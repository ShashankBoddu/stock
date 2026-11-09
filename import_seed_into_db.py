"""Import the clean, verified stockroom inventory into the database."""
from scripts.import_fresh_inventory import run_import

if __name__ == "__main__":
    run_import()
