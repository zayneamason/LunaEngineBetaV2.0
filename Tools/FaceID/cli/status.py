#!/usr/bin/env python3
"""
FaceID Status CLI
=================

Shows what's in the face database — enrolled entities, 
embedding counts, access tiers, and recent identity events.

Usage:
    python status.py
    python status.py --log 20
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import FaceDatabase


def main():
    parser = argparse.ArgumentParser(description="Show FaceID database status")
    parser.add_argument("--db", default=None, help="Path to face database")
    parser.add_argument("--log", type=int, default=10, help="Number of recent log entries to show")
    args = parser.parse_args()
    
    with FaceDatabase(args.db) as db:
        entities = db.list_entities()
        total_embeddings = db.count_embeddings()
        
        print(f"\n{'='*60}")
        print(f"  LUNA FACEID STATUS")
        print(f"{'='*60}")
        print(f"  Database:    {db.db_path}")
        print(f"  Entities:    {len(entities)}")
        print(f"  Embeddings:  {total_embeddings}")
        print(f"{'='*60}\n")
        
        if entities:
            print("  ENROLLED ENTITIES")
            print(f"  {'Name':<16} {'Luna Tier':<12} {'DR Tier':<10} {'Faces':<8}")
            print(f"  {'-'*46}")
            for e in entities:
                print(f"  {e['entity_name']:<16} {e['luna_tier']:<12} {e['dataroom_tier']:<10} {e['face_count']:<8}")
        else:
            print("  No entities enrolled. Run: python cli/enroll.py --name \"YourName\"")
        
        # Recent log entries
        rows = db._conn.execute(
            "SELECT * FROM identity_log ORDER BY created_at DESC LIMIT ?",
            (args.log,)
        ).fetchall()
        
        if rows:
            print(f"\n  RECENT EVENTS (last {args.log})")
            print(f"  {'Time':<22} {'Event':<16} {'Entity':<14} {'Details'}")
            print(f"  {'-'*70}")
            for row in rows:
                name = row['entity_name'] or '—'
                details = row['details'] or ''
                if len(details) > 30:
                    details = details[:30] + '...'
                print(f"  {row['created_at']:<22} {row['event_type']:<16} {name:<14} {details}")
        
        print()


if __name__ == "__main__":
    main()
