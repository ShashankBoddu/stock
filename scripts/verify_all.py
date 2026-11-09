import urllib.request
import urllib.parse
import json
import http.cookiejar
import sys

BASE = "http://127.0.0.1:8080"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def api(path, method="GET", data=None):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with opener.open(req) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        err_content = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_content)
        except Exception:
            return e.code, {"error": err_content}

def run_tests():
    print("--- 1. Testing Network Info & Setup Status ---")
    st, res = api("/api/network-info")
    assert st == 200, f"network-info failed: {st} {res}"
    print("Network info OK:", res.get("primary_wifi_url"))

    st, res = api("/api/setup-status")
    assert st == 200, f"setup-status failed: {st} {res}"
    print("Setup status OK, setup_required:", res.get("setup_required"))

    print("\n--- 2. Testing Authentication ---")
    # Login as stock person (from database, let's find user)
    import sqlite3
    conn = sqlite3.connect("data/inventory.sqlite3")
    conn.row_factory = sqlite3.Row
    stock_user = conn.execute("SELECT * FROM users WHERE role='stock' AND active=1").fetchone()
    emp_user = conn.execute("SELECT * FROM users WHERE role='employee' AND active=1").fetchone()
    print("Stock user:", stock_user["name"], stock_user["email"])
    print("Employee user:", emp_user["name"] if emp_user else "None", emp_user["email"] if emp_user else "None")

    # We can create a direct session in DB to test with both roles cleanly
    import secrets, time
    stock_token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO sessions(token, user_id, expires_at) VALUES(?,?,?)", (stock_token, stock_user["id"], int(time.time())+3600))
    conn.commit()

    # Test bootstrap with stock person session
    cookie = http.cookiejar.Cookie(version=0, name="stock_session", value=stock_token, port=None, port_specified=False, domain="127.0.0.1", domain_specified=False, domain_initial_dot=False, path="/", path_specified=True, secure=False, expires=None, discard=True, comment=None, comment_url=None, rest={"HttpOnly": None}, rfc2109=False)
    cj.set_cookie(cookie)

    st, bootstrap = api("/api/bootstrap")
    assert st == 200, f"bootstrap failed: {st} {bootstrap}"
    print("Bootstrap OK. Total items:", len(bootstrap["data"]["items"]))
    print("Overview:", bootstrap["data"]["overview"])

    print("\n--- 3. Testing High-Rack extraction on items ---")
    items = bootstrap["data"]["items"]
    items_with_racks = [i for i in items if i.get("high_racks")]
    print(f"Items with high_racks assigned: {len(items_with_racks)} / {len(items)}")
    racks = set()
    for i in items:
        for r in i.get("high_racks", []):
            racks.add(r)
    print("Discovered high racks:", sorted(list(racks)))

    print("\n--- 4. Testing Purchase Request Lifecycle ---")
    # Create a test purchase request
    req_payload = {
        "purpose": "Unit test request",
        "lines": [
            {"item_name": "Test SMD Resistor 4.7k", "quantity": 10, "vendor": "Mouser", "product_url": "https://mouser.com/test"}
        ]
    }
    st, res = api("/api/requests", method="POST", data=req_payload)
    assert st == 201, f"Create request failed: {st} {res}"
    print("Request created successfully")

    # Refresh bootstrap to find the created request
    _, b = api("/api/bootstrap")
    req = next(r for r in b["data"]["requests"] if r["purpose"] == "Unit test request")
    req_id = req["id"]
    print(f"Created request ID: {req_id}, Ref: {req['ref']}, Status: {req['status']}")

    # Transition: pending -> approved
    st, res = api(f"/api/requests/{req_id}/status", method="POST", data={"status": "approved"})
    assert st == 200, f"Approve failed: {st} {res}"
    print("Approved OK")

    # Transition: approved -> ordered
    st, res = api(f"/api/requests/{req_id}/status", method="POST", data={"status": "ordered"})
    assert st == 200, f"Order failed: {st} {res}"
    print("Ordered OK")

    # Test receiving partial quantity (3 of 10)
    leaf_loc = next(l for l in b["data"]["locations"] if l["is_leaf"])
    line_id = req["lines"][0]["id"]
    st, res = api(f"/api/requests/{req_id}/receive", method="POST", data={
        "line_id": line_id,
        "quantity": 3,
        "location_id": leaf_loc["id"],
        "name": "Test SMD Resistor 4.7k",
        "category": "SMD Resistors"
    })
    assert st == 200, f"Receive failed: {st} {res}"
    print("Received 3 units OK")

    # Verify status is now partially_received
    _, b = api("/api/bootstrap")
    req = next(r for r in b["data"]["requests"] if r["id"] == req_id)
    assert req["status"] == "partially_received", f"Expected partially_received, got {req['status']}"
    print("Status correctly transitioned to partially_received")

    # Test "Close remaining" (status -> received)
    st, res = api(f"/api/requests/{req_id}/status", method="POST", data={"status": "received"})
    assert st == 200, f"Close remaining failed: {st} {res}"
    print("Close remaining OK")

    _, b = api("/api/bootstrap")
    req = next(r for r in b["data"]["requests"] if r["id"] == req_id)
    assert req["status"] == "received", f"Expected received, got {req['status']}"
    print("Status correctly set to received")

    # Now test delete_request on a request that has received inward transactions
    st, res = api(f"/api/requests/{req_id}/delete", method="POST", data={})
    assert st == 200, f"Delete received request failed: {st} {res}"
    print("Safe close/delete on received request returned:", res.get("message"))

    # Now create another dummy request and test full deletion (0 received)
    st, res = api("/api/requests", method="POST", data={
        "purpose": "Dummy cancellation test",
        "lines": [{"item_name": "Dummy Capacitor", "quantity": 5}]
    })
    assert st == 201
    _, b = api("/api/bootstrap")
    dummy_req = next(r for r in b["data"]["requests"] if r["purpose"] == "Dummy cancellation test")
    dummy_id = dummy_req["id"]
    
    # Test Cancel order (status -> rejected)
    st, res = api(f"/api/requests/{dummy_id}/status", method="POST", data={"status": "rejected"})
    assert st == 200, f"Cancel dummy request failed: {st} {res}"
    print("Cancelled dummy request OK")

    # Test permanent delete of unreceived request
    st, res = api(f"/api/requests/{dummy_id}/delete", method="POST", data={})
    assert st == 200, f"Permanent delete failed: {st} {res}"
    print("Permanent delete dummy request OK:", res.get("message"))

    # Verify dummy request is completely gone
    _, b = api("/api/bootstrap")
    assert not any(r["id"] == dummy_id for r in b["data"]["requests"]), "Dummy request was not deleted!"
    print("Dummy request confirmed deleted from database")

    print("\n--- 5. Testing Active Loans & Clear Loan ---")
    # Take an item to create a loan
    test_item = next(i for i in b["data"]["items"] if i["total_qty"] > 5 and not i["needs_count"])
    avail_loc = next(l for l in test_item["locations"] if l["quantity"] > 0 and not l["needs_count"])
    
    st, res = api("/api/transactions", method="POST", data={
        "kind": "issue",
        "issue_type": "already_taken",
        "item_id": test_item["id"],
        "location_id": avail_loc["id"],
        "quantity": 1,
        "purpose": "Loan clearing test"
    })
    assert st == 201, f"Take item failed: {st} {res}"
    print(f"Issued 1 unit of '{test_item['name']}' to create test loan")

    _, b = api("/api/bootstrap")
    active_loan = next(l for l in b["data"]["loans"] if l["item_id"] == test_item["id"])
    loan_id = active_loan["id"]
    print(f"Active loan ID: {loan_id}, remaining: {active_loan['remaining_qty']}")

    # Test clearing the loan
    st, res = api(f"/api/loans/{loan_id}/clear", method="POST", data={})
    assert st == 200, f"Clear loan failed: {st} {res}"
    print("Clear loan OK:", res.get("message"))

    # Verify active loans list no longer includes this loan
    _, b = api("/api/bootstrap")
    assert not any(l["id"] == loan_id for l in b["data"]["loans"]), "Loan should no longer be active!"
    print("Loan confirmed cleared from active loans")

    # Clean up test items/data
    conn.execute("UPDATE stock SET quantity=quantity+1 WHERE item_id=? AND location_id=?", (test_item["id"], avail_loc["id"]))
    conn.execute("DELETE FROM stock WHERE item_id IN (SELECT id FROM items WHERE name='Test SMD Resistor 4.7k')")
    conn.execute("DELETE FROM transactions WHERE purpose LIKE '%Unit test%' OR purpose LIKE '%Loan clearing%' OR purpose LIKE '%Checkout cleared by stock person%' OR item_id IN (SELECT id FROM items WHERE name='Test SMD Resistor 4.7k')")
    conn.execute("DELETE FROM request_lines WHERE request_id=?", (req_id,))
    conn.execute("DELETE FROM purchase_requests WHERE id=?", (req_id,))
    conn.execute("DELETE FROM loans WHERE id=?", (loan_id,))
    conn.execute("DELETE FROM items WHERE name='Test SMD Resistor 4.7k'")
    conn.execute("DELETE FROM sessions WHERE token=?", (stock_token,))
    conn.commit()
    conn.close()

    print("\n=== ALL AUTOMATED TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_tests()
