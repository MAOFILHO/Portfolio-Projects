"""A sample diff, so the demo has something to say without the viewer writing code.

Deliberately plants one finding per specialist: a string-interpolated SQL query
(security), a duplicated/renamed helper with a stale comment (style), and new
error handling with no test covering it (tests).
"""

from __future__ import annotations

SAMPLE_DIFF = '''\
diff --git a/api/orders.py b/api/orders.py
--- a/api/orders.py
+++ b/api/orders.py
@@ -12,9 +12,26 @@ from .db import connection
 def get_order(order_id: str):
     with connection() as conn:
         return conn.execute(
             "SELECT * FROM orders WHERE id = ?", (order_id,)
         ).fetchone()
+
+
+def search_orders(customer_email: str, status: str):
+    """Look up orders. Fast path: skips the ORM."""
+    with connection() as conn:
+        query = (
+            "SELECT * FROM orders WHERE customer_email = '"
+            + customer_email
+            + "' AND status = '"
+            + status
+            + "'"
+        )
+        return conn.execute(query).fetchall()
+
+
+def find_orders(customer_email: str, status: str):
+    """Look up orders. Fast path: skips the ORM."""
+    return search_orders(customer_email, status)
+
+
+def cancel_order(order_id: str, requested_by: str):
+    order = get_order(order_id)
+    if order is None:
+        raise ValueError(f"No order {order_id}")
+    with connection() as conn:
+        conn.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
+    return {"cancelled": order_id, "by": requested_by}
diff --git a/tests/test_orders.py b/tests/test_orders.py
--- a/tests/test_orders.py
+++ b/tests/test_orders.py
@@ -4,3 +4,7 @@ from api.orders import get_order
 def test_get_order_returns_none_for_missing_id():
     assert get_order("nope") is None
+
+
+def test_cancel_order_marks_it_cancelled():
+    assert cancel_order("ord-1", "admin") == {"cancelled": "ord-1", "by": "admin"}
'''
