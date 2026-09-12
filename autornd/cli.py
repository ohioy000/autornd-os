"""CLI for AutoRnD — doc ingestion, knowledge stats, episodic memory."""

import argparse
import sys
from pathlib import Path


def cmd_ingest(args):
    """Ingest documents into the ChromaDB knowledge store."""
    from autornd.knowledge.store import ingest_directory, ingest_file, get_stats

    target = Path(args.path)
    if target.is_file():
        count = ingest_file(target)
        print(f"Ingested {count} chunks from {target}")
    elif target.is_dir():
        count = ingest_directory(target)
        print(f"Ingested {count} total chunks from {target}")
    else:
        print(f"Error: {target} not found", file=sys.stderr)
        sys.exit(1)

    stats = get_stats()
    print(f"Knowledge store: {stats['count']} total chunks")


def cmd_stats(args):
    """Show knowledge store statistics."""
    from autornd.knowledge.store import get_stats
    stats = get_stats()
    print(f"Collection: {stats['collection']}")
    print(f"Chunks: {stats['count']}")
    if "status" in stats:
        print(f"Status: {stats['status']}")


def cmd_query(args):
    """Query the knowledge store."""
    from autornd.knowledge.store import retrieve
    results = retrieve(args.query, n_results=args.n)
    if not results:
        print("No results found. Have you run 'ingest' yet?")
        return
    for i, r in enumerate(results, 1):
        print(f"\n--- Result {i} (distance: {r['distance']:.3f}, source: {r['tag']}) ---")
        print(r["text"][:500])


def cmd_ingest_docs(args):
    """Ingest project documentation for the active profile."""
    from autornd.knowledge.store import ingest_directory, get_stats
    from autornd.profiles import get_profile, list_profiles, load_profile, set_profile

    if hasattr(args, "profile") and args.profile:
        set_profile(load_profile(args.profile))

    profile = get_profile()
    docs_dir = Path(__file__).parent.parent / "docs" / profile.get_docs_dir()
    if not docs_dir.exists():
        print(f"Error: docs directory not found: {docs_dir}", file=sys.stderr)
        available = list_profiles()
        if available:
            print(f"Available profiles: {', '.join(available)}", file=sys.stderr)
        sys.exit(1)

    count = ingest_directory(docs_dir)
    print(f"Ingested {count} chunks from docs/{profile.get_docs_dir()}/")

    stats = get_stats()
    print(f"Knowledge store: {stats['count']} total chunks")


def main():
    parser = argparse.ArgumentParser(
        prog="autornd",
        description="AutoRnD CLI — Engineering & R&D Agentic Team",
    )
    sub = parser.add_subparsers(dest="command")

    p_ingest = sub.add_parser("ingest", help="Ingest docs into knowledge store")
    p_ingest.add_argument("path", help="File or directory to ingest")
    p_ingest.set_defaults(func=cmd_ingest)

    p_init = sub.add_parser("init-knowledge", help="Ingest project documentation")
    p_init.add_argument("--profile", help="Profile name (overrides AUTORND_PROFILE)")
    p_init.set_defaults(func=cmd_ingest_docs)

    p_stats = sub.add_parser("stats", help="Knowledge store statistics")
    p_stats.set_defaults(func=cmd_stats)

    p_query = sub.add_parser("query", help="Query knowledge store")
    p_query.add_argument("query", help="Search query")
    p_query.add_argument("-n", type=int, default=5, help="Number of results")
    p_query.set_defaults(func=cmd_query)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
