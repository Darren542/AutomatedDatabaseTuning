import os
from dotenv import load_dotenv

def main() -> int:
    load_dotenv()
    # POC placeholder: implement Query Store + DMV extraction here.
    # Output should populate feature store tables (e.g., dbo.Autotuner_QueryStats, dbo.Autotuner_IndexUsage).
    print("Collector placeholder. Next: connect to SQL Server and extract Query Store + DMV metrics.")
    host = os.getenv("SQLSERVER_HOST", "localhost")
    db = os.getenv("SQLSERVER_DATABASE", "AutotunerDemo")
    print(f"Configured target: {host} / {db}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
