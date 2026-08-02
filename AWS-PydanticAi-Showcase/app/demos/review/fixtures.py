"""Sample diffs, so the demo has something to say without the viewer writing code.

Five languages, so a viewer can compare how the specialists behave across
Python, C#/.NET, Java, and TypeScript rather than taking "it's language-agnostic"
on faith. Each one deliberately plants one finding per specialist: a security
defect (SQL injection, a hardcoded credential, path traversal / insecure
deserialization, or reflected XSS), a style issue, and new behavior with no
test covering it.
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

PYTHON_SAMPLE_DIFF = """\
diff --git a/api/users.py b/api/users.py
--- a/api/users.py
+++ b/api/users.py
@@ -5,6 +5,20 @@ from .db import get_connection
 def get_user(user_id):
     conn = get_connection()
     return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

+@app.route("/admin/users/search")
+def search_users():
+    email = request.args.get("email")
+    conn = get_connection()
+    query = "SELECT * FROM users WHERE email LIKE '%" + email + "%'"
+    return jsonify([dict(r) for r in conn.execute(query).fetchall()])
+
+
+@app.route("/admin/users/<user_id>/promote", methods=["POST"])
+def promote_user(user_id):
+    conn = get_connection()
+    conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))
+    conn.commit()
+    return jsonify({"promoted": user_id})
"""

CSHARP_SAMPLE_DIFF = """\
diff --git a/Controllers/AccountController.cs b/Controllers/AccountController.cs
--- a/Controllers/AccountController.cs
+++ b/Controllers/AccountController.cs
@@ -8,6 +8,22 @@ public class AccountController : ControllerBase
     private readonly IAccountService _accounts;

+    private const string ConnString =
+        "Server=prod-sql-01;Database=Accounts;User Id=sa;Password=Sup3rSecret!;";
+
+    [HttpPost("close")]
+    public IActionResult CloseAccount(string accountId)
+    {
+        using var conn = new SqlConnection(ConnString);
+        conn.Open();
+        var cmd = new SqlCommand(
+            $"UPDATE Accounts SET Status = 'Closed' WHERE Id = '{accountId}'", conn);
+        cmd.ExecuteNonQuery();
+        return Ok(new { closed = accountId });
+    }
 }
"""

JAVA_SAMPLE_DIFF = """\
diff --git a/src/main/java/com/acme/FileController.java b/src/main/java/com/acme/FileController.java
--- a/src/main/java/com/acme/FileController.java
+++ b/src/main/java/com/acme/FileController.java
@@ -1,3 +1,24 @@
+package com.acme;
+
+import java.io.*;
+import org.springframework.web.bind.annotation.*;
+
+@RestController
+public class FileController {
+
+    @GetMapping("/files/download")
+    public byte[] download(@RequestParam String name) throws IOException {
+        File file = new File("/var/data/exports/" + name);
+        return java.nio.file.Files.readAllBytes(file.toPath());
+    }
+
+    @PostMapping("/files/import")
+    public Object importData(@RequestBody byte[] data) throws Exception {
+        ObjectInputStream in = new ObjectInputStream(new ByteArrayInputStream(data));
+        return in.readObject();
+    }
+}
"""

TYPESCRIPT_SAMPLE_DIFF = """\
diff --git a/src/routes/search.ts b/src/routes/search.ts
--- a/src/routes/search.ts
+++ b/src/routes/search.ts
@@ -1,3 +1,18 @@
+import { Router } from "express";
+
+const router = Router();
+
+router.get("/search", (req, res) => {
+  const q = req.query.q as string;
+  res.send(`<html><body>Results for: ${q}</body></html>`);
+});
+
+router.get("/search/count", (req, res) => {
+  const q = req.query.q as string;
+  res.send(`<html><body>${q}: ${countMatches(q)} results</body></html>`);
+});
+
+export default router;
"""

SAMPLE_DIFFS: dict[str, str] = {
    "sample1": SAMPLE_DIFF,
    "python": PYTHON_SAMPLE_DIFF,
    "csharp": CSHARP_SAMPLE_DIFF,
    "java": JAVA_SAMPLE_DIFF,
    "typescript": TYPESCRIPT_SAMPLE_DIFF,
}
