import pathlib

KB_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "data" / "kb"

# 文件 -> content_type(建库材料清单,CLI 与录入页同读这一份)
SOURCE_TYPES = {
    "product-faq.md": "faq",
    "returns-policy.md": "policy",
    "after-sales-manual.md": "manual",
    "product-specs.md": "spec",
}

CONTENT_TYPES = ("faq", "policy", "manual", "spec")

