Recommended placement:

- `sql/databases/wwi/setup/poc_prepare_demo_baseline.sql`
- `sql/databases/wwi/setup/poc_cleanup_restore_demo.sql`

How to use for demo:
1. Run `poc_prepare_demo_baseline.sql`
2. Run your workload + baseline capture
3. Apply/test index recommendations
4. Run `poc_cleanup_restore_demo.sql` after the demo

Why this approach:
- It gives you a deliberately worse starting point for a clearer before/after demo
- It keeps the change reversible by rebuilding the disabled WWI index
- It separates WWI-specific demo manipulation from your shared/universal scripts
