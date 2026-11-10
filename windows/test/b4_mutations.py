"""B4 mutations in isolated profile copies; no real Windows system changes."""
from mutations import mutant


def probe(label, file, old, new, test):
    mutant(label, file, old, new, command=['-m', 'unittest', 'test_b4.B4.' + test, '-v'])


def main():
    probe('F2 trigger delay removed', 'dienst-einrichten.ps1',
          "    $logon.Delay = 'PT30S'\n", '', 'test_logon_task_delay_and_fixed_script')
    probe('F2 one lock call without verification', 'jnpt-sperren.ps1',
          'if ([Jnpt.SessionLock]::IsLocked()) { return 0 }',
          'return 0', 'test_unlocked_after_all_attempts_is_failure')
    probe('F3 no autologon polling', 'dienst-einrichten.ps1',
          'if ($attempt -eq 20)', 'if ($attempt -eq 0)',
          'test_autologon_delayed_registry_values_are_confirmed')
    probe('N2 raw missing-file message', 'dienst-einrichten.ps1',
          "        throw 'Docker Desktop einmal in jnpt-dienst starten und die Einstellungen pruefen (AutoStart an, 2375 aus, Auto-Update aus)'",
          '        $null = $null', 'test_missing_settings_real_file_adapter_has_fixed_message_and_error_exit')
    probe('F2 foreign explorer accepted', 'jnpt-sperren.ps1',
          'Where-Object { $_.SessionId -eq $sessionId }',
          'Where-Object { $true }', 'test_foreign_explorer_cannot_allow_lock_and_wait_is_bounded')
    probe('F2 failed lock reported as success', 'jnpt-sperren.ps1',
          '    return 1\n', '    return 0\n', 'test_unlocked_after_all_attempts_is_failure')
    probe('F2 unlocked WTS flag accepted', 'jnpt-sperren.ps1',
          'Marshal.ReadInt32(buffer, 16) == WTS_SESSIONSTATE_LOCK',
          'true', 'test_wts_adapter_decodes_only_locked_current_session_and_frees_buffer')
    probe('F2 errors disclose data', 'jnpt-sperren.ps1',
          'catch { exit 1 }', 'catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }',
          'test_native_failure_is_silent_and_nonzero')
    for command in ['logoff.exe', 'shutdown.exe /s']:
        probe('F2 forbidden fallback ' + command, 'jnpt-sperren.ps1',
              '    return 1\n', '    ' + command + '\n    return 1\n',
              'test_unlocked_after_all_attempts_is_failure')
    print('B4: 10 mutations killed; original bytes unchanged.', flush=True)


if __name__ == '__main__':
    main()
