"""CLI tool for validating and registering multi-source document collections into PostgreSQL.

Usage:
    python scripts/register_corpus.py --dry-run
    python scripts/register_corpus.py --cuad-limit 50 --maud-limit 25
"""
import argparse
import asyncio
from pathlib import Path

from apps.api.app.core.database import AsyncSessionLocal

from packages.ingestion.registry import DocumentRegistrar
from packages.ingestion.scanner import scan_directory
from packages.ingestion.validator import CorpusValidator
from packages.schemas.common import DocumentSourceType


async def main():
    parser = argparse.ArgumentParser(description="Corpus Validation & Registration Pipeline")
    parser.add_argument(
        "--sec-dir", type=str, default="sec_10k_dataset", help="Path to SEC 10-K directory"
    )
    parser.add_argument(
        "--cuad-dir",
        type=str,
        default="legal_datasets/cuad/extracted/CUAD_v1/full_contract_txt",
        help="Path to CUAD contracts directory",
    )
    parser.add_argument(
        "--cuad-limit",
        type=int,
        default=50,
        help="Max CUAD contracts to register (25-50 recommended)",
    )
    parser.add_argument(
        "--maud-dir",
        type=str,
        default="legal_datasets/maud/extracted/data/contracts",
        help="Path to MAUD contracts directory",
    )
    parser.add_argument(
        "--maud-limit", type=int, default=25, help="Max MAUD contracts to register"
    )
    parser.add_argument(
        "--acord-file",
        type=str,
        default="legal_datasets/acord/extracted/ACORD Dataset & ReadMe (external)/corpus.jsonl",
        help="Path to ACORD corpus.jsonl file",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate without committing to database"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("ENTERPRISE RAG -- CORPUS VALIDATION & REGISTRATION")
    print(f"Mode: {'DRY RUN (Validation only)' if args.dry_run else 'ACTIVE (Registration to DB)'}")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        validator = CorpusValidator(session)
        total_valid = 0
        total_duplicates = 0
        total_invalid = 0

        # 1. SEC 10-K Filings
        sec_dir = Path(args.sec_dir)
        if sec_dir.is_dir():
            sec_files = scan_directory(sec_dir, allowed_extensions={".html", ".htm"})
            print(f"\nScanning SEC 10-K: Discovered {len(sec_files)} files...")
            sec_report = await validator.validate_collection(sec_files, DocumentSourceType.SEC)
            print(
                f"   [OK] Valid: {sec_report.valid_count} | "
                f"[DUP] Duplicates: {sec_report.duplicate_count} | "
                f"[ERR] Invalid: {sec_report.invalid_count}"
            )
            companies_str = ", ".join(list(sec_report.by_company.keys()))
            print(f"   Companies ({len(sec_report.by_company)}): [{companies_str}]")
            print(f"   Years: {sorted(sec_report.by_year.keys())}")
            total_valid += sec_report.valid_count
            total_duplicates += sec_report.duplicate_count
            total_invalid += sec_report.invalid_count

            if not args.dry_run:
                registrar = DocumentRegistrar(session)
                for res in sec_report.valid_files:
                    await registrar.register_document(res)
                await session.commit()
                print(f"   [SAVED] Registered {sec_report.valid_count} SEC documents.")

        # 2. CUAD Commercial Contracts
        cuad_dir = Path(args.cuad_dir)
        if cuad_dir.is_dir():
            cuad_files = scan_directory(cuad_dir, allowed_extensions={".txt", ".pdf"})
            if args.cuad_limit:
                cuad_files = cuad_files[: args.cuad_limit]
            print(f"\nScanning CUAD: Discovered {len(cuad_files)} contracts...")
            cuad_report = await validator.validate_collection(cuad_files, DocumentSourceType.CUAD)
            print(
                f"   [OK] Valid: {cuad_report.valid_count} | "
                f"[DUP] Duplicates: {cuad_report.duplicate_count} | "
                f"[ERR] Invalid: {cuad_report.invalid_count}"
            )
            total_valid += cuad_report.valid_count
            total_duplicates += cuad_report.duplicate_count
            total_invalid += cuad_report.invalid_count

            if not args.dry_run:
                registrar = DocumentRegistrar(session)
                for res in cuad_report.valid_files:
                    await registrar.register_document(res)
                await session.commit()
                print(f"   [SAVED] Registered {cuad_report.valid_count} CUAD contracts.")

        # 3. MAUD Merger Agreements
        maud_dir = Path(args.maud_dir)
        if maud_dir.is_dir():
            maud_files = scan_directory(maud_dir, allowed_extensions={".txt"})
            if args.maud_limit:
                maud_files = maud_files[: args.maud_limit]
            print(f"\nScanning MAUD: Discovered {len(maud_files)} merger agreements...")
            maud_report = await validator.validate_collection(maud_files, DocumentSourceType.MAUD)
            print(
                f"   [OK] Valid: {maud_report.valid_count} | "
                f"[DUP] Duplicates: {maud_report.duplicate_count} | "
                f"[ERR] Invalid: {maud_report.invalid_count}"
            )
            total_valid += maud_report.valid_count
            total_duplicates += maud_report.duplicate_count
            total_invalid += maud_report.invalid_count

            if not args.dry_run:
                registrar = DocumentRegistrar(session)
                for res in maud_report.valid_files:
                    await registrar.register_document(res)
                await session.commit()
                print(f"   [SAVED] Registered {maud_report.valid_count} MAUD contracts.")

        # 4. ACORD Legal Clause Benchmark
        acord_file = Path(args.acord_file)
        if acord_file.is_file():
            print(f"\nScanning ACORD: Found benchmark corpus at {acord_file.name}...")
            acord_res = await validator.validate_file(acord_file, DocumentSourceType.ACORD)
            print(f"   Status: {acord_res.status.value.upper()}")
            if acord_res.status.value == "valid":
                total_valid += 1
                if not args.dry_run:
                    registrar = DocumentRegistrar(session)
                    await registrar.register_document(acord_res)
                    await session.commit()
                    print("   [SAVED] Registered ACORD benchmark corpus in PostgreSQL.")

        print("\n" + "=" * 60)
        print("SUMMARY")
        print(f"   Total Valid Documents:      {total_valid}")
        print(f"   Total Duplicate Documents:  {total_duplicates}")
        print(f"   Total Invalid Files:        {total_invalid}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
