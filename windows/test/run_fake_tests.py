"""CI/local selection: PS 5.1 fakes and Compose config, no running containers."""
import sys
import unittest

# These existing integration tests need a Linux engine; keep them in the
# separate full adapter selection documented in README.md.
ENGINE_TESTS = {
    'test_profile.Profile.test_mail_empty_secret_compose_adapter',
    'test_profile.Profile.test_leaf_properties_and_partial_pair_rejection',
    'test_profile.Profile.test_caddy_adapter_and_https_rejections',
    'test_operator_docs.RecoveryDocs.test_n4_helper_preserves_files_and_nonroot_key',
}


def cases(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from cases(test)
        elif test.id() not in ENGINE_TESTS:
            yield test


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.discover('windows/test')
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(cases(suite)))
    sys.exit(not result.wasSuccessful())
