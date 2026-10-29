"""kb-preview:材料清单与就地切块预览(dry-run,不写库)。"""
from app.kb import documents
from app.kb.sources import KB_DIR, SOURCE_TYPES


def main() -> None:
    total = 0
    for fname, ctype in SOURCE_TYPES.items():
        md = (KB_DIR / fname).read_text(encoding="utf-8")
        chunks = documents.build_chunks(md, content_type=ctype)
        tables = sum(1 for c in chunks if c.answer.lstrip().startswith("|"))
        key = sum(1 for c in chunks if c.is_key_clause)
        total += len(chunks)
        print(f"  {fname}: {len(chunks)} 块 (关键条款 {key}, 表格块 {tables})")
    print(f"材料清单共 {total} 块(仅预览,未入库)")


if __name__ == "__main__":
    main()

