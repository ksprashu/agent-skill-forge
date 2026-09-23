#!/usr/bin/env python3
# Copyright 2026 Agent Skill Forge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the two ways ``fetch_upstream.py`` used to install the wrong bytes.

1. A download interrupted partway left a directory with some of a skill in it.
   The next run saw a non-empty directory, called it a cache hit, and
   materialised the truncation -- then hashed the truncation into the manifest,
   so ``--verify`` cheerfully agreed it was fine. ``--offline`` could never
   recover, because it has nothing to re-check against.

2. When a fetch failed, both installers deliberately carried on to the sync
   step so that local skills still land. But the copy under ``.upstream/`` from
   the *previous* pin was still sitting there, so the sync linked it while the
   log said the new pin had failed. An install one commit behind what the lock
   file claims, reported as a failure that changed nothing.

Everything here is offline. No test in this file touches the network.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import fetch_upstream as F  # noqa: E402


ENTRY = {
    "repo": "example/skills",
    "path": "skills/demo",
    "ref": "a" * 40,
    "license": "MIT",
    "attribution": "Example",
}


def write_skill(root, body="Do the thing.\n"):
    """A minimal but overlay-compatible skill tree."""
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("---\nname: demo\ndescription: A demo skill.\n---\n\n" + body)
    return root


class CacheTestCase(unittest.TestCase):
    """Redirects both the cache and the materialise root into a tempdir.

    ``materialise_root`` resolves against the module-level ``REPO_ROOT``, so
    without the patch below these tests would write real directories into the
    working copy.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="forge-fetch-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        self._real_repo_root = F.REPO_ROOT
        F.REPO_ROOT = self.tmp
        self.addCleanup(setattr, F, "REPO_ROOT", self._real_repo_root)

        self.lock = {
            "cache_dir": os.path.join(self.tmp, "cache"),
            "materialise_dir": "upstream",
            "skills": {"demo": dict(ENTRY)},
        }

    def cached(self, entry=None):
        return F.cache_path(self.lock, entry or ENTRY)

    def dest(self, name="demo"):
        return os.path.join(F.materialise_root(self.lock), name)


class TestCacheCompleteness(CacheTestCase):
    def test_empty_directory_is_not_a_hit(self):
        os.makedirs(self.cached())
        self.assertFalse(F.cache_is_complete(self.cached()))

    def test_truncated_download_is_not_a_hit(self):
        """Files but no SKILL.md and no marker: exactly what a mid-walk network
        failure leaves behind, since fetch_tree writes as it goes."""
        os.makedirs(os.path.join(self.cached(), "references"))
        with open(os.path.join(self.cached(), "references", "a.md"), "w") as f:
            f.write("half of it\n")
        self.assertFalse(F.cache_is_complete(self.cached()))

    def test_marked_directory_is_a_hit(self):
        write_skill(self.cached())
        with open(os.path.join(self.cached(), F.CACHE_COMPLETE_MARKER), "w") as f:
            json.dump({"files": 1}, f)
        self.assertTrue(F.cache_is_complete(self.cached()))

    def test_pre_marker_cache_is_adopted_once_and_stamped(self):
        """The migration allowance. A cache from before the marker existed
        cannot prove itself, so a top-level SKILL.md stands in -- otherwise
        --offline on an air-gapped box with a warm cache has no way forward."""
        write_skill(self.cached())
        marker = os.path.join(self.cached(), F.CACHE_COMPLETE_MARKER)
        self.assertFalse(os.path.exists(marker))

        self.assertTrue(F.cache_is_complete(self.cached()))
        self.assertTrue(os.path.exists(marker),
                        "adoption must stamp the marker so it is a one-time cost")

        # Second call takes the marker path, not the migration path.
        self.assertTrue(F.cache_is_complete(self.cached()))

    def test_marker_is_not_copied_into_the_materialised_skill(self):
        """It belongs to the cache. If it rode along, tree_sha256 would hash
        something that is not part of the skill."""
        write_skill(self.cached())
        with open(os.path.join(self.cached(), F.CACHE_COMPLETE_MARKER), "w") as f:
            json.dump({"files": 1}, f)

        dest, manifest = F.materialise(self.lock, "demo", dict(ENTRY), self.cached())
        self.assertFalse(os.path.exists(os.path.join(dest, F.CACHE_COMPLETE_MARKER)))
        self.assertEqual(manifest["tree_sha256"], F.tree_hash(dest))


class TestAtomicPromotion(CacheTestCase):
    def test_a_failed_fetch_leaves_no_visible_cache(self):
        """fetch_tree_atomic stages in a sibling directory, so a raising fetch
        never publishes anything under the real name for a later run to trust."""
        calls = []

        def boom(repo, path, ref, token, dest, depth=0):
            calls.append(dest)
            write_skill(dest)  # some of it landed before the failure
            raise F.FetchError("connection reset")

        real = F.fetch_tree
        F.fetch_tree = boom
        self.addCleanup(setattr, F, "fetch_tree", real)

        with self.assertRaises(F.FetchError):
            F.fetch_tree_atomic(ENTRY["repo"], ENTRY["path"], ENTRY["ref"],
                                None, self.cached())

        self.assertTrue(calls, "the staging directory should have been used")
        self.assertNotEqual(calls[0], self.cached(),
                            "must download into staging, not the final path")
        self.assertFalse(os.path.exists(self.cached()))
        self.assertFalse(F.cache_is_complete(self.cached()))

    def test_a_successful_fetch_publishes_and_marks(self):
        def ok(repo, path, ref, token, dest, depth=0):
            write_skill(dest)
            return 1

        real = F.fetch_tree
        F.fetch_tree = ok
        self.addCleanup(setattr, F, "fetch_tree", real)

        n = F.fetch_tree_atomic(ENTRY["repo"], ENTRY["path"], ENTRY["ref"],
                                None, self.cached())
        self.assertEqual(n, 1)
        self.assertTrue(F.cache_is_complete(self.cached()))

    def test_promotion_replaces_an_older_cache_at_the_same_path(self):
        write_skill(self.cached(), body="stale\n")

        def ok(repo, path, ref, token, dest, depth=0):
            write_skill(dest, body="fresh\n")
            return 1

        real = F.fetch_tree
        F.fetch_tree = ok
        self.addCleanup(setattr, F, "fetch_tree", real)

        F.fetch_tree_atomic(ENTRY["repo"], ENTRY["path"], ENTRY["ref"],
                            None, self.cached())
        text = Path(self.cached(), "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("fresh", text)
        self.assertNotIn("stale", text)

    def test_no_partial_directories_are_left_behind(self):
        def boom(repo, path, ref, token, dest, depth=0):
            write_skill(dest)
            raise F.FetchError("nope")

        real = F.fetch_tree
        F.fetch_tree = boom
        self.addCleanup(setattr, F, "fetch_tree", real)

        with self.assertRaises(F.FetchError):
            F.fetch_tree_atomic(ENTRY["repo"], ENTRY["path"], ENTRY["ref"],
                                None, self.cached())

        parent = os.path.dirname(self.cached())
        leftovers = [n for n in os.listdir(parent) if "partial" in n]
        self.assertEqual(leftovers, [], f"staging not cleaned up: {leftovers}")


class TestStaleMaterialisation(CacheTestCase):
    def materialise_at(self, ref):
        entry = dict(ENTRY, ref=ref)
        cached = self.cached(entry)
        write_skill(cached)
        with open(os.path.join(cached, F.CACHE_COMPLETE_MARKER), "w") as f:
            json.dump({"files": 1}, f)
        return F.materialise(self.lock, "demo", entry, cached)

    def test_reads_the_ref_out_of_the_manifest(self):
        self.materialise_at("b" * 40)
        self.assertEqual(F.materialised_ref(self.lock, "demo"), "b" * 40)

    def test_absent_skill_has_no_ref(self):
        self.assertIsNone(F.materialised_ref(self.lock, "demo"))

    def test_corrupt_manifest_has_no_ref(self):
        self.materialise_at("b" * 40)
        with open(os.path.join(self.dest(), F.MANIFEST_NAME), "w") as f:
            f.write("{not json")
        self.assertIsNone(F.materialised_ref(self.lock, "demo"))

    def test_a_matching_pin_survives(self):
        """A fetch can fail for a skill that is already materialised at exactly
        the ref we want -- a flaky network on a re-run. Deleting a correct copy
        would turn a no-op into a regression."""
        self.materialise_at("b" * 40)
        self.assertIsNone(F.drop_stale_materialisation(self.lock, "demo", "b" * 40))
        self.assertTrue(os.path.isdir(self.dest()))

    def test_a_changed_pin_is_removed(self):
        self.materialise_at("b" * 40)
        old = F.drop_stale_materialisation(self.lock, "demo", "c" * 40)
        self.assertEqual(old, "b" * 40)
        self.assertFalse(os.path.exists(self.dest()),
                         "the sync step would otherwise install the old pin")

    def test_an_unreadable_manifest_is_removed(self):
        """Cannot prove it is current, so it does not get the benefit of the
        doubt. The sync step cannot tell the difference either."""
        self.materialise_at("b" * 40)
        os.remove(os.path.join(self.dest(), F.MANIFEST_NAME))
        self.assertEqual(F.drop_stale_materialisation(self.lock, "demo", "b" * 40),
                         "unknown")
        self.assertFalse(os.path.exists(self.dest()))

    def test_nothing_materialised_is_not_an_error(self):
        self.assertIsNone(F.drop_stale_materialisation(self.lock, "demo", "c" * 40))


if __name__ == "__main__":
    unittest.main()
