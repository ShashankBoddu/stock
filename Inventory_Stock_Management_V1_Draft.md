# Inventory Stock Management — V1 Working Draft

Status: interview draft; decisions can still change.

## Goal

Provide a free-to-run, simple stock system with a clear overview that staff can open on Android phones, iPhones, and office computers. Use the existing stock spreadsheets as the starting inventory, while keeping every confirmed stock movement traceable.

## V1 access and hosting

- Run the application on the stock person's existing office laptop and make it available over the office network.
- All nine users can view stock. The stock person must keep the laptop on for the live application to be available.
- Start with office access. Remote live access is deferred; do not expose the application to the public internet in V1.
- HTTP on the office network is accepted for V1. This means traffic, including any sign-in details, is not encrypted on the network; this is a known deployment limitation.
- Do not require phone-side offline transaction entry in V1. Earlier offline capture was relaxed because it adds HTTPS setup. If the connection to the office laptop is unavailable, stock movements cannot be recorded in the live app.
- Provide a read-only Google Sheets overview as a fallback while the laptop is off. It is owned by a personal Gmail account with company approval, shared only as a read-only view, and contains item, quantity by location, low-stock status, and last-updated time. Do not put employee transaction history or purchase details in that sheet.
- Refresh the overview automatically when the application is online. If the laptop or internet is unavailable, the sheet remains a dated snapshot.
- Target no recurring software or hosting subscription. Existing hardware, electricity, and internet costs are outside this target.

## Users and responsibilities

- Every employee uses an individual company email identity. All nine users can view the inventory.
- Employees can record stock issues directly. Each issue records the signed-in recorder and the selected recipient, project, item, quantity, and exact storage location. The corresponding location quantity decreases immediately, and both people appear in movement history.
- Employees choose a project from a list managed by the stock person; include a `General/Internal` choice.
- Employees can submit purchase requests, including requests for an item not yet in the catalog.
- Each requested item can be entered manually, with optional vendor and product link. The request records the signed-in requester and selected project.
- Employees can record the return of reusable equipment. A return stays pending until the stock person confirms the item is back and usable; if rejected, the loan becomes active again.
- Inward entries stay pending until the stock person confirms or rejects receipt. Only confirmed receipts increase available stock.
- The stock person manages item records, can move an item's balance between storage locations while editing it, manages project choices and minimum stock levels, confirms inward entries and asset returns, and records stock corrections. They also source approved purchases and add new items to inventory when received.
- Managers do not need application accounts. A manager approves or rejects a request outside the app. The stock person records the Approved/Rejected status; the app records the stock person's account and timestamp.

## Inventory and locations

- Keep one item record per distinct item/specification, with a unique Item ID.
- Show an item's total quantity and its quantity at each storage location.
- Represent storage as a folder-style hierarchy using the labels from the supplied stock lists, for example `Stock Room / IoT Rack-C / C-3 / BOX -21`. Show the complete path wherever staff browse or move stock.
- Use whole-number quantities, with a unit such as Nos.
- Keep reusable equipment/tools distinct from consumable stock. Track who has reusable assets and record their returns.
- The stock person can set a minimum quantity per item. Show low-stock alerts only for items with a minimum configured.
- Search and filter by item and location; provide a dashboard for total items, current stock, low stock, pending inward/return confirmations, and pending purchase requests.

## Initial data

- Combine `stock_list.xlsx` and `Stock_List_030325.xlsx` using their Markdown exports for review/import.
- Match likely duplicates by name/specification while preserving source locations. Do not add overlapping quantities automatically.
- Preserve blank or conflicting quantities as `Needs physical count`, not zero. The stock person verifies these counts before they are treated as confirmed stock.
- Keep source notes available for the stock person to review during cleanup.
- Current import result: 1,152 catalog items, 190 locations, 1,187 item/location rows, and 291 opening transactions totaling 1,342 known units.
- 869 catalog items are flagged for physical count. Legacy-only quantities remain reference notes and are not counted as available stock. Five possible spelling duplicates are listed for review.

## Purchase flow

1. Employee submits an item and required quantity in the Purchase section. Existing catalog items can be selected; a new item can be entered by name/details.
2. Request status starts as Pending.
3. A manager decides outside the app. The stock person records Approved or Rejected.
4. For an approved request, the stock person marks it Ordered.
5. When goods arrive, the stock person records the received quantity and confirms receipt. New items are added to the catalog at this point.
6. Approval alone never changes available stock.

V1 does not require in-app manager approval, supplier purchase-order generation, price tracking, invoice attachments, or detailed partial-delivery tracking. These can be reconsidered later.

## Notifications and later phases

- Use in-app request statuses and dashboard alerts only in V1. No email or WhatsApp integration.
- Defer QR labels to a later phase.
- Revisit offline phone entry, remote access, and QR labels after the office-only system is usable.

## Implementation decisions still open

- Confirm the local database and application stack during implementation.
- Confirm how employee email identities are provisioned and authenticated. HTTP has been accepted for V1, but password logins over HTTP are exposed to other parties on the same network.
- Confirm whether all employee email addresses can open the read-only Google Sheet, or whether some need Google accounts.
- Agree on the setup procedure, laptop startup, local network address, and backup location before putting live stock data into use.
