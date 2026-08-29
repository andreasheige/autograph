import argparse

from src.agents.vault_graph_indexer import VaultGraphIndexer


def main():
    parser = argparse.ArgumentParser(
        description="Create stable navigation hubs and indexes for the vault graph."
    )
    parser.parse_args()
    VaultGraphIndexer().run()


if __name__ == "__main__":
    main()
