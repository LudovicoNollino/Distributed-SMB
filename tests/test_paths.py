from distributed_smb.shared.paths import ASSETS_DIR, MARIO1_ASSETS_DIR, PACKAGE_ROOT


def test_shared_asset_paths_resolve_package_resources():
    assert PACKAGE_ROOT.name == "distributed_smb"
    assert ASSETS_DIR == PACKAGE_ROOT / "assets"
    assert MARIO1_ASSETS_DIR == ASSETS_DIR / "mario1"
    assert (MARIO1_ASSETS_DIR / "Mario.png").exists()
