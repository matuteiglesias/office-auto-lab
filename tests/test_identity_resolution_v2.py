from __future__ import annotations

import unittest

from office_runtime.office.identity import IdentityResolutionError, IdentityResolver


def snapshot(*, bindings=None, workspaces=None) -> dict:
    return {
        "tables": {
            "front_registry_v2": {
                "rows": [
                    {
                        "front_id": "fr_0003",
                        "title": "Office Auto Lab",
                        "repo_path": "/wrong/legacy/path",
                        "workdir": "/also/wrong",
                    },
                    {"front_id": "fr_human", "title": "Human-only front"},
                ]
            },
            "REPO MONITOR_v2": {
                "rows": bindings
                if bindings is not None
                else [
                    {
                        "binding_id": "rb_0002",
                        "front_id": "fr_0003",
                        "repo_id": "repo.office-auto-lab",
                        "workspace_id": "ws_0134",
                        "binding_role": "PRIMARY_IMPLEMENTATION",
                        "is_primary": "TRUE",
                        "binding_status": "ACTIVE",
                        "_primary_local_path": "/untrusted/convenience/path",
                    }
                ]
            },
            "repo_workspaces_v2": {
                "rows": workspaces
                if workspaces is not None
                else [
                    {
                        "workspace_id": "ws_0134",
                        "repo_id": "repo.office-auto-lab",
                        "local_path": "/home/matias/repos/office-auto-lab",
                        "checkout_kind": "CHECKOUT",
                        "workspace_status": "ACTIVE",
                        "is_preferred": "TRUE",
                    }
                ]
            },
        }
    }


class IdentityResolverV2Tests(unittest.TestCase):
    def test_execution_path_comes_only_from_repo_workspace_chain(self) -> None:
        context = IdentityResolver(snapshot()).execution_context("fr_0003")

        self.assertEqual(context["path_authority"], "repo_workspaces_v2")
        self.assertEqual(context["primary_repository"]["repo_id"], "repo.office-auto-lab")
        self.assertEqual(
            context["primary_repository"]["workspace"]["local_path"],
            "/home/matias/repos/office-auto-lab",
        )
        self.assertNotEqual(context["primary_repository"]["workspace"]["local_path"], "/wrong/legacy/path")
        self.assertNotEqual(context["primary_repository"]["workspace"]["local_path"], "/untrusted/convenience/path")

    def test_binding_without_workspace_id_uses_unique_preferred_active_workspace(self) -> None:
        bindings = [
            {
                "binding_id": "rb_1",
                "front_id": "fr_0003",
                "repo_id": "repo.office-auto-lab",
                "workspace_id": "",
                "binding_role": "PRIMARY_IMPLEMENTATION",
                "is_primary": "TRUE",
                "binding_status": "ACTIVE",
            }
        ]
        workspaces = [
            {
                "workspace_id": "ws_archive",
                "repo_id": "repo.office-auto-lab",
                "local_path": "/archive/office",
                "checkout_kind": "ARCHIVE",
                "workspace_status": "ACTIVE",
                "is_preferred": "FALSE",
            },
            {
                "workspace_id": "ws_live",
                "repo_id": "repo.office-auto-lab",
                "local_path": "/repos/office",
                "checkout_kind": "CHECKOUT",
                "workspace_status": "ACTIVE",
                "is_preferred": "TRUE",
            },
        ]

        context = IdentityResolver(snapshot(bindings=bindings, workspaces=workspaces)).execution_context("fr_0003")
        self.assertEqual(context["primary_repository"]["workspace"]["workspace_id"], "ws_live")
        self.assertEqual(context["primary_repository"]["workspace"]["status"], "RESOLVED")

    def test_multiple_active_workspaces_without_unique_preference_stay_ambiguous(self) -> None:
        bindings = [
            {
                "binding_id": "rb_1",
                "front_id": "fr_0003",
                "repo_id": "repo.office-auto-lab",
                "workspace_id": "",
                "binding_role": "PRIMARY_IMPLEMENTATION",
                "is_primary": "TRUE",
                "binding_status": "ACTIVE",
            }
        ]
        workspaces = [
            {
                "workspace_id": "ws_a",
                "repo_id": "repo.office-auto-lab",
                "local_path": "/repos/a",
                "checkout_kind": "CHECKOUT",
                "workspace_status": "ACTIVE",
                "is_preferred": "FALSE",
            },
            {
                "workspace_id": "ws_b",
                "repo_id": "repo.office-auto-lab",
                "local_path": "/repos/b",
                "checkout_kind": "CHECKOUT",
                "workspace_status": "ACTIVE",
                "is_preferred": "FALSE",
            },
        ]

        context = IdentityResolver(snapshot(bindings=bindings, workspaces=workspaces)).execution_context("fr_0003")
        self.assertEqual(context["primary_repository"]["workspace"]["status"], "AMBIGUOUS")
        self.assertIsNone(context["primary_repository"]["workspace"]["local_path"])

    def test_multiple_preferred_workspaces_are_contract_error(self) -> None:
        bindings = [
            {
                "binding_id": "rb_1",
                "front_id": "fr_0003",
                "repo_id": "repo.office-auto-lab",
                "workspace_id": "",
                "binding_role": "PRIMARY_IMPLEMENTATION",
                "is_primary": "TRUE",
                "binding_status": "ACTIVE",
            }
        ]
        workspaces = [
            {
                "workspace_id": "ws_a",
                "repo_id": "repo.office-auto-lab",
                "local_path": "/repos/a",
                "checkout_kind": "CHECKOUT",
                "workspace_status": "ACTIVE",
                "is_preferred": "TRUE",
            },
            {
                "workspace_id": "ws_b",
                "repo_id": "repo.office-auto-lab",
                "local_path": "/repos/b",
                "checkout_kind": "CHECKOUT",
                "workspace_status": "ACTIVE",
                "is_preferred": "TRUE",
            },
        ]

        resolver = IdentityResolver(snapshot(bindings=bindings, workspaces=workspaces))
        with self.assertRaises(IdentityResolutionError):
            resolver.execution_context("fr_0003")

    def test_explicit_workspace_must_belong_to_bound_repo(self) -> None:
        bindings = [
            {
                "binding_id": "rb_1",
                "front_id": "fr_0003",
                "repo_id": "repo.office-auto-lab",
                "workspace_id": "ws_wrong",
                "binding_role": "PRIMARY_IMPLEMENTATION",
                "is_primary": "TRUE",
                "binding_status": "ACTIVE",
            }
        ]
        workspaces = [
            {
                "workspace_id": "ws_wrong",
                "repo_id": "repo.other",
                "local_path": "/repos/other",
                "checkout_kind": "CHECKOUT",
                "workspace_status": "ACTIVE",
                "is_preferred": "TRUE",
            }
        ]

        resolver = IdentityResolver(snapshot(bindings=bindings, workspaces=workspaces))
        with self.assertRaises(IdentityResolutionError):
            resolver.execution_context("fr_0003")

    def test_human_only_front_resolves_without_inventing_repository(self) -> None:
        context = IdentityResolver(snapshot()).execution_context("fr_human")
        self.assertEqual(context["repositories"], [])
        self.assertIsNone(context["primary_repository"])

    def test_multiple_primary_bindings_are_contract_error(self) -> None:
        bindings = [
            {
                "binding_id": "rb_1",
                "front_id": "fr_0003",
                "repo_id": "repo.office-auto-lab",
                "workspace_id": "ws_0134",
                "binding_role": "PRIMARY_IMPLEMENTATION",
                "is_primary": "TRUE",
                "binding_status": "ACTIVE",
            },
            {
                "binding_id": "rb_2",
                "front_id": "fr_0003",
                "repo_id": "repo.second",
                "workspace_id": "ws_second",
                "binding_role": "SUPPORTING",
                "is_primary": "TRUE",
                "binding_status": "ACTIVE",
            },
        ]
        workspaces = [
            {
                "workspace_id": "ws_0134",
                "repo_id": "repo.office-auto-lab",
                "local_path": "/repos/office",
                "checkout_kind": "CHECKOUT",
                "workspace_status": "ACTIVE",
                "is_preferred": "TRUE",
            },
            {
                "workspace_id": "ws_second",
                "repo_id": "repo.second",
                "local_path": "/repos/second",
                "checkout_kind": "CHECKOUT",
                "workspace_status": "ACTIVE",
                "is_preferred": "TRUE",
            },
        ]

        resolver = IdentityResolver(snapshot(bindings=bindings, workspaces=workspaces))
        with self.assertRaises(IdentityResolutionError):
            resolver.execution_context("fr_0003")


if __name__ == "__main__":
    unittest.main()
