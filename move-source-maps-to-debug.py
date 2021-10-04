#!/usr/bin/env python3
import os

def main():
    for source_dir, dirnames, filenames in os.walk("/app"):
        if source_dir == "/app/lib":
            dirnames.remove("debug")

        for name in filenames:
            if name.endswith(".js.map"):
                source_path = os.path.join(source_dir, name)
                target_dir = os.path.join("/app/lib/debug", source_dir[len("/app/"):])
                target_path = os.path.join(target_dir, name)
                os.makedirs(target_dir, exist_ok=True)
                os.rename(source_path, target_path)
                os.symlink(target_path, source_path)


if __name__ == "__main__":
    main()
