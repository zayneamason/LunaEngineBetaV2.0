"""
Smoke Tests for Luna Engine
===========================

These tests verify critical paths work end-to-end.
They use real database connections (in-memory or temp files)
and only mock external APIs (Claude, Groq, etc.).

Run with: pytest tests/smoke -v -m smoke
"""
