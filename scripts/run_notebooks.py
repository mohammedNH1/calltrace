"""Execute the notebooks in their documented order and save their outputs in place."""

from __future__ import annotations

import nbformat
from nbclient import NotebookClient

from calltrace.config import PROJECT_ROOT


def main() -> None:
    directory = PROJECT_ROOT / "notebooks"
    for path in sorted(directory.glob("0*.ipynb")):
        print(f"Executing {path.name}", flush=True)
        notebook = nbformat.read(path, as_version=4)
        NotebookClient(notebook, timeout=3600, kernel_name="python3",
                       resources={"metadata": {"path": str(directory)}}).execute()
        nbformat.write(notebook, path)
    print("All notebooks executed.")


if __name__ == "__main__":
    main()
