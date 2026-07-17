"""Seeds a few sample products on local startup, so the Shop page has
something to show immediately rather than requiring a manual "Add sample
products" click. Idempotent — only inserts if the table is empty, so
restarting an already-seeded dev database never duplicates rows.

Kept identical to monolith/app/seed.py's sample data on purpose — same
catalog on both sides of the migration story, so a before/after comparison
in the Shop page is meaningful."""
from . import db
from .models import Product

SAMPLE_PRODUCTS = [
    ("Contoso Mug", "contoso-mug", 1299),
    ("Contoso T-Shirt", "contoso-tshirt", 2499),
    ("Contoso Notebook", "contoso-notebook", 899),
    ("Contoso Water Bottle", "contoso-water-bottle", 1899),
    ("Contoso Backpack", "contoso-backpack", 5499),
    ("Contoso Laptop Sleeve", "contoso-laptop-sleeve", 2999),
    ("Contoso Baseball Cap", "contoso-baseball-cap", 2199),
    ("Contoso Hoodie", "contoso-hoodie", 4499),
    ("Contoso Sticker Pack", "contoso-sticker-pack", 599),
    ("Contoso Desk Mat", "contoso-desk-mat", 2699),
    ("Contoso Wireless Mouse", "contoso-wireless-mouse", 3499),
    ("Contoso Mechanical Keyboard", "contoso-mechanical-keyboard", 7999),
    ("Contoso Desk Lamp", "contoso-desk-lamp", 3299),
    ("Contoso Phone Case", "contoso-phone-case", 1699),
    ("Contoso USB-C Charger", "contoso-usb-c-charger", 2499),
    ("Contoso Tote Bag", "contoso-tote-bag", 1499),
    ("Contoso Beanie", "contoso-beanie", 1899),
    ("Contoso Travel Mug", "contoso-travel-mug", 1999),
    ("Contoso Notepad Set", "contoso-notepad-set", 1299),
    ("Contoso Pen Set", "contoso-pen-set", 999),
    ("Contoso Monitor Stand", "contoso-monitor-stand", 4299),
    ("Contoso Webcam Cover", "contoso-webcam-cover", 499),
    ("Contoso Fleece Jacket", "contoso-fleece-jacket", 6499),
    ("Contoso Sneakers", "contoso-sneakers", 8999),
]


def seed_products_if_empty() -> None:
    if Product.query.count() > 0:
        return
    for name, slug, price in SAMPLE_PRODUCTS:
        db.session.add(Product(name=name, slug=slug, price=price))
    db.session.commit()
