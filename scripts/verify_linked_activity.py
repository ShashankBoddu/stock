import urllib.request, json, sqlite3, secrets, time

BASE = 'http://127.0.0.1:8080'

# Create sessions in DB
conn = sqlite3.connect('data/inventory.sqlite3')
conn.row_factory = sqlite3.Row
stock_user = conn.execute("SELECT * FROM users WHERE role='stock' AND active=1").fetchone()
emp_user = conn.execute("SELECT * FROM users WHERE role='employee' AND active=1").fetchone()

stock_token = secrets.token_urlsafe(32)
emp_token = secrets.token_urlsafe(32)
now_ts = int(time.time()) + 3600
conn.execute("INSERT INTO sessions(token, user_id, expires_at) VALUES(?,?,?)", (stock_token, stock_user["id"], now_ts))
conn.execute("INSERT INTO sessions(token, user_id, expires_at) VALUES(?,?,?)", (emp_token, emp_user["id"], now_ts))
conn.commit()

def request(path, data=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Cookie'] = f'stock_session={token}'
    body = json.dumps(data).encode('utf-8') if data is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=body, headers=headers)
    with urllib.request.urlopen(req) as res:
        return res.status, json.loads(res.read().decode('utf-8'))

print("Sessions initialized for", stock_user["name"], "and", emp_user["name"])

# 1. Bootstrap data
_, boot = request('/api/bootstrap', token=emp_token)
items = boot['data']['items']
target_item = next(i for i in items if i['total_qty'] >= 10 and not i['needs_count'])
target_loc = target_item['locations'][0]['id']
print(f"Target item for test: {target_item['name']} (ID {target_item['id']}), Location {target_loc}, Current Qty {target_item['total_qty']}")

# 2. Shashank takes 10 units (already_taken)
take_payload = {
    'kind': 'issue',
    'item_id': target_item['id'],
    'location_id': target_loc,
    'quantity': 10,
    'issue_type': 'already_taken',
    'purpose': 'Testing linked lifecycle'
}
_, take_res = request('/api/transactions', take_payload, token=emp_token)
print("Shashank took 10 units OK")

# 3. Check bootstrap: verify checkouts list and active loan
_, boot_after_take = request('/api/bootstrap', token=emp_token)
my_loan = next(l for l in boot_after_take['data']['loans'] if l['item_id'] == target_item['id'] and l['remaining_qty'] == 10)
loan_id = my_loan['id']
print(f"Checkout loan created with ID {loan_id}, remaining: {my_loan['remaining_qty']}")

# 4. Shashank returns 3 units to shelf (creates pending return)
return_payload = {
    'quantity': 3,
    'location_id': target_loc,
    'condition': 'Unused 3 pieces'
}
_, _ = request(f'/api/loans/{loan_id}/return', return_payload, token=emp_token)
print(f"Return 3 units requested for loan {loan_id}")

# 5. Stock person confirms the return
_, boot_stock = request('/api/bootstrap', token=stock_token)
ret_tx = next(t for t in boot_stock['data']['transactions'] if t['kind'] == 'return' and t['related_request_id'] == -loan_id and t['status'] == 'pending')
_, _ = request(f'/api/transactions/{ret_tx["id"]}/confirm', {}, token=stock_token)
print(f"Stock person confirmed return tx {ret_tx['id']}")

# 6. Verify loan remaining_qty is now 7
_, boot_mid = request('/api/bootstrap', token=emp_token)
loan_mid = next(l for l in boot_mid['data']['loans'] if l['id'] == loan_id)
assert loan_mid['remaining_qty'] == 7, f"Expected 7 remaining, got {loan_mid['remaining_qty']}"
print(f"Loan {loan_id} remaining qty updated to 7 OK")

# 7. Shashank marks 4 units as used in project
consume_payload = {
    'quantity': 4,
    'purpose': 'Used in prototype PCB testing'
}
_, _ = request(f'/api/loans/{loan_id}/consume', consume_payload, token=emp_token)
print("Marked 4 units as used in project OK")

# 8. Verify loan remaining_qty is now 3, consumed_qty is 4
_, boot_after_consume = request('/api/bootstrap', token=emp_token)
loan_consumed = next(l for l in boot_after_consume['data']['loans'] if l['id'] == loan_id)
assert loan_consumed['remaining_qty'] == 3, f"Expected 3 remaining, got {loan_consumed['remaining_qty']}"
assert loan_consumed['consumed_qty'] == 4, f"Expected 4 consumed, got {loan_consumed['consumed_qty']}"
print(f"Loan {loan_id} state verified: remaining = 3, consumed = 4")

# 9. Stock person returns remaining 3 units directly
_, _ = request(f'/api/loans/{loan_id}/return', {'quantity': 3, 'location_id': target_loc}, token=stock_token)
print("Stock person returned final 3 units back to shelf")

# 10. Check that the loan is now closed in 'loans', but preserved in 'checkouts'
_, boot_final = request('/api/bootstrap', token=emp_token)
active_loans = [l for l in boot_final['data']['loans'] if l['id'] == loan_id]
assert len(active_loans) == 0, "Loan should no longer be active"

completed_checkout = next(c for c in boot_final['data']['checkouts'] if c['id'] == loan_id)
assert completed_checkout['status'] == 'returned', "Checkout status should be 'returned'"
assert completed_checkout['remaining_qty'] == 0, "Checkout remaining_qty should be 0"
assert completed_checkout['consumed_qty'] == 4, "Checkout consumed_qty should be 4"
print("Checkout lifecycle in checkouts verified: status=returned, remaining=0, consumed=4")

# 11. Verify all transactions are linked to this loan
linked_txs = [t for t in boot_final['data']['transactions'] if t.get('related_request_id') == -loan_id]
kinds = [t['kind'] for t in linked_txs]
print(f"Linked transactions for checkout {loan_id}: {kinds}")
assert 'issue' in kinds, "Issue tx should be linked"
assert 'return' in kinds, "Return tx should be linked"
assert 'consumed' in kinds, "Consumed tx should be linked"

# 12. Clean up test checkout and restore physical stock
with sqlite3.connect('data/inventory.sqlite3') as c_clean:
    c = c_clean.cursor()
    c.execute("DELETE FROM transactions WHERE related_request_id=?", (-loan_id,))
    c.execute("DELETE FROM loans WHERE id=?", (loan_id,))
    c.execute("DELETE FROM sessions WHERE token IN (?,?)", (stock_token, emp_token))
    # Restore the 4 consumed units back to target location
    c.execute("UPDATE stock SET quantity=quantity+4 WHERE item_id=? AND location_id=?", (target_item['id'], target_loc))
    c_clean.commit()
print("Cleaned up test loan, sessions & restored stock cleanly.")
print("\n=== LINKED ACTIVITY LIFECYCLE TEST PASSED 100%! ===")
