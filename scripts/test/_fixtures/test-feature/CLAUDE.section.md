### Test Feature (fixture)

This section is inserted by the test-feature fixture during install_feature
and removed during uninstall_feature. It exists only to exercise the
marker-based CLAUDE.md patching logic.

- Install entry point: `./scripts/enable-feature.sh test-feature`
- Removal: `./scripts/disable-feature.sh test-feature`
