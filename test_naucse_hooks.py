import unittest

import pytest

from naucse_hooks import normalize_repo, same_repo, get_branch_from_ref


@pytest.mark.parametrize("denormalized,normalized", [
    ("https://github.com/baxterthehacker/public-repo.git", "github.com/baxterthehacker/public-repo"),
    ("https://github.com/baxterthehacker/public-repo", "github.com/baxterthehacker/public-repo"),
    ("http://github.com/baxterthehacker/public-repo.git", "github.com/baxterthehacker/public-repo"),
    ("http://github.com/baxterthehacker/public-repo", "github.com/baxterthehacker/public-repo"),
])
def test_normalize_repo(denormalized, normalized):
    assert normalize_repo(denormalized) == normalized


@pytest.mark.parametrize("repo1,repo2,same", [
    ("https://github.com/baxterthehacker/public-repo.git", "https://github.com/baxterthehacker/public-repo.git", True),
    ("https://github.com/baxterthehacker/public-repo.git", "https://github.com/baxterthehacker/public-repo", True),
    ("https://github.com/baxterthehacker/public-repo.git", "http://github.com/baxterthehacker/public-repo.git", True),
    ("https://github.com/baxterthehacker/public-repo.git", "http://github.com/baxterthehacker/public-repo", True),
    ("https://github.com/baxterthehacker/public-repo", "https://github.com/baxterthehacker/public-repo.git", True),
    ("https://github.com/baxterthehacker/public-repo", "https://github.com/baxterthehacker/public-repo.git", True),
    ("https://github.com/baxterthehacker/public-repo", "https://github.com/baxterthehacker/public-repo.git", True),
    ("https://github.com/baxterthehacker/public-repo", "https://github.com/baxterthehacker/public-repo.git", True),
    ("https://github.com/baxterthehacker/public-repo.git", "https://github.com/baxthehacker/public-repo.git", False),
    ("https://github.com/baxterthehacker/public-repo.git", "https://github.com/baxterthehacker/public.git", False),
])
def test_same_repo(repo1, repo2, same):
    assert same_repo(repo1, repo2) == same


@pytest.mark.parametrize("ref,branch", [
    ("refs/heads/master", "master"),
    ("refs/heads/master_branch", "master_branch"),
    ("refs/tags/v1.0", None),
    ("refs/remotes/origin/master", None),
    ("asdfasdf", None)

])
def test_get_branch_from_ref(ref, branch):
    assert get_branch_from_ref(ref) == branch
