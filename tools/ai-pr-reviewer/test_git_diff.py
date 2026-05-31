import unittest

from git_diff import (
    GitDiffError,
    _binary_paths_from_diff,
    _merge_changed_files,
    parse_name_status_z,
)
from review_contract import ChangedFile


class GitDiffParserTests(unittest.TestCase):
    def test_parse_name_status_z_supports_common_statuses(self):
        output = (
            b"A\0new.py\0"
            b"M\0mod.py\0"
            b"D\0old.py\0"
            b"R100\0oldname.py\0newname.py\0"
            b"C100\0src.py\0copy.py\0"
            b"T\0kind\0"
            b"U\0conflict\0"
            b"X\0mystery\0"
        )

        self.assertEqual(
            parse_name_status_z(output),
            [
                ChangedFile(path="new.py", status="added"),
                ChangedFile(path="mod.py", status="modified"),
                ChangedFile(path="old.py", status="deleted"),
                ChangedFile(path="newname.py", status="renamed", old_path="oldname.py"),
                ChangedFile(path="copy.py", status="copied", old_path="src.py"),
                ChangedFile(path="kind", status="type_changed"),
                ChangedFile(path="conflict", status="unmerged"),
                ChangedFile(path="mystery", status="unknown"),
            ],
        )

    def test_parse_name_status_z_rejects_truncated_records(self):
        with self.assertRaises(GitDiffError):
            parse_name_status_z(b"R100\0oldname.py\0")

    def test_binary_paths_are_detected_from_diff_text(self):
        diff = "\n".join(
            [
                "diff --git a/image.png b/image.png",
                "index 1111111..2222222 100644",
                "GIT binary patch",
                "literal 5",
            ]
        )

        files = _merge_changed_files(
            [ChangedFile(path="image.png", status="modified")],
            _binary_paths_from_diff(diff),
        )

        self.assertEqual(files, [ChangedFile(path="image.png", status="modified", is_binary=True)])

    def test_merge_dedupes_local_staged_and_unstaged_entries(self):
        files = _merge_changed_files(
            [
                ChangedFile(path="app.py", status="modified"),
                ChangedFile(path="app.py", status="modified"),
            ],
            set(),
        )

        self.assertEqual(files, [ChangedFile(path="app.py", status="modified")])


if __name__ == "__main__":
    unittest.main()
