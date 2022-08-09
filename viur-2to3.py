#!/usr/bin/python3
"""
Naive ViUR3 project porting script with a simple search & replace mechanism using lookup table.
"""

import os, argparse, difflib

# Naive lookup table. Could be done better later...
lookup = {
    "onItemAdded": "onAdded",
    "onItemEdited": "onEdited",
    "onItemDeleted": "onDeleted",
    "addItemSuccess": "addSuccess",
    "editItemSuccess": "editSuccess",
    "from server import": "from viur.core import"
}

bones = [
    "base",
    "boolean",
    "captcha",
    "color",
    "credential",
    "date",
    "email",
    "file",
    "key",
    "numeric",
    "password",
    "randomslice",
    "raw",
    "record",
    "relational",
    "selectcountry",
    "select",
    "sortindex",
    "spatial",
    "string",
    "text",
    "treeleaf",
    "treenode",
    "user"
]

lookup.update({
    f"{name}Bone": f"{name[0].upper()}{name[1:]}Bone" for name in bones
})

if __name__ == "__main__":
    # Get arguments
    ap = argparse.ArgumentParser(
        description="ViUR2-to-ViUR3 porting tool"
    )

    ap.add_argument(
        "project_root",
        type=str,
        help="ViUR project root"
    )

    ap.add_argument(
        "-d", "--dryrun",
        action="store_true",
        help="Dry-run for testing, don't modify files"
    )
    ap.add_argument(
        "-x", "--daredevil",
        action="store_true",
        help="Don't make backups of files, just replace and deal with it"
    )

    args = ap.parse_args()

    # Iterate all files in current folder
    for root, dirs, files in os.walk(args.project_root):
        # Ignore ViUR library folders
        if any(ignore in root for ignore in ["viur", "flare", "html5"]):
            continue

        for filename in files:
            # Ignore anything without a .py-extension
            ext = os.path.splitext(filename)[1].lower()[1:]
            if ext not in ["py"]:
                continue

            filename = os.path.join(root, filename)

            with open(filename, "r") as f:
                original_content = content = f.read()

            count = 0
            for k, v in lookup.items():
                if k in content:
                    content = content.replace(k, v)
                    count += 1

            if count:
                if not args.dryrun:
                    if not args.daredevil:
                        os.rename(filename, filename + ".bak")

                    with open(filename, "w") as f:
                        f.write(content)

                    print("Modified %r" % filename)
                else:
                    print(
                        "\n".join(
                            difflib.unified_diff(
                                original_content.splitlines(),
                                content.splitlines(),
                                filename,
                                filename
                            )
                        )
                    )
