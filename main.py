#!/usr/bin/env python3
from Bootstrap import Terraform_bootstrap


def main():
    try:
        boot = Terraform_bootstrap()
        boot.start()
        print("✅ Bootstrap completed successfully")
    except Exception as e:
        print(f"❌ An error occurred: {e}")
        exit(1)


if __name__ == "__main__":
    main()
