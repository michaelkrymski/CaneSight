"""CS-023 adapter integration with fake driver devices; never opens GPIO."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import signal
import unittest
from unittest.mock import Mock, patch

from edge.haptic_gpio import GPIOOutput, bench, main
from edge.haptics import CHANNELS, HapticScheduler


class Device:
    def __init__(self, pin, events):
        self.pin, self.events = pin, events
        self.value = False
        self.fail = set()

    def _event(self, action):
        self.events.append((self.pin, action))
        if action in self.fail:
            raise OSError('Synthetic private driver details')

    def on(self):
        self._event('on')
        self.value = True

    def off(self):
        self._event('off')
        self.value = False

    def close(self):
        self._event('close')


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.events, self.devices = [], {}
        self.now = 0
        self.clock = lambda: self.now

    def factory(self, pin, **kwargs):
        self.assertEqual(kwargs, dict(active_high=True, initial_value=False))
        self.events.append((pin, 'open-off'))
        device = Device(pin, self.events)
        self.devices[pin] = device
        return device

    def output(self):
        output = GPIOOutput(left_bcm=17, right_bcm=27, active_high=True,
                            device_factory=self.factory)
        self.addCleanup(output.close)
        return output

    def scheduler(self, output):
        scheduler = HapticScheduler(output, clock=self.clock)
        self.addCleanup(scheduler.close)
        scheduler.set_ready(True)
        self.now = 200
        return scheduler

    def test_initialization_off_and_scheduler_channels_map_to_explicit_pins(self):
        output = self.output()
        self.assertEqual(self.events, [(17, 'open-off'), (27, 'open-off')])
        scheduler = self.scheduler(output)
        self.assertTrue(scheduler.pulse('left', 100, valid_until_ms=500))
        self.assertTrue(self.devices[17].value)
        self.assertFalse(self.devices[27].value)
        self.assertTrue(scheduler.pulse('right', 200, valid_until_ms=500))
        self.now = 300
        result = scheduler.tick()
        self.assertEqual(result['outputs'], dict(left=False, right=True))
        self.assertEqual(result['mode'], 'gpio')
        self.assertTrue(result['gpio_used'])
        self.now = 400
        self.assertEqual(scheduler.tick()['outputs'], dict.fromkeys(CHANNELS, False))

    def test_invalid_pins_polarity_and_reserved_button_never_open_devices(self):
        for left, right in ((True, 27), ('17', 27), (1, 27), (17, 28),
                            (17, 17), (21, 27), (17, 21)):
            with self.subTest(left=left, right=right), self.assertRaises(ValueError):
                GPIOOutput(left_bcm=left, right_bcm=right, active_high=True,
                           device_factory=self.factory)
        for polarity in (False, 1, None, 'high'):
            with self.subTest(polarity=polarity), self.assertRaises(ValueError):
                GPIOOutput(left_bcm=17, right_bcm=27, active_high=polarity,
                           device_factory=self.factory)
        self.assertEqual(self.events, [])

    def test_partial_initialization_stops_and_releases_first_pin(self):
        def factory(pin, **kwargs):
            if pin == 27:
                raise OSError('Synthetic private details')
            return self.factory(pin, **kwargs)
        with self.assertRaises(RuntimeError) as error:
            GPIOOutput(left_bcm=17, right_bcm=27, active_high=True, device_factory=factory)
        self.assertNotIn('private', str(error.exception))
        self.assertEqual(self.events, [(17, 'open-off'), (17, 'off'), (17, 'close')])

    def test_interrupt_during_initialization_releases_acquired_pin(self):
        def factory(pin, **kwargs):
            if pin == 27:
                raise KeyboardInterrupt()
            return self.factory(pin, **kwargs)
        with self.assertRaises(KeyboardInterrupt):
            GPIOOutput(left_bcm=17, right_bcm=27, active_high=True, device_factory=factory)
        self.assertEqual(self.events[-2:], [(17, 'off'), (17, 'close')])

    def test_pair_start_failure_turns_peer_off_and_latches_both_layers(self):
        output = self.output()
        scheduler = self.scheduler(output)
        self.devices[27].fail.add('on')
        self.assertFalse(scheduler.pulse(CHANNELS, valid_until_ms=500))
        self.assertFalse(any(device.value for device in self.devices.values()))
        self.assertIsNotNone(scheduler.fault)
        self.assertFalse(scheduler.set_ready(True))
        with self.assertRaises(RuntimeError):
            output.write('left', True)

    def test_failed_off_is_unknown_and_does_not_skip_peer_or_cleanup(self):
        output = self.output()
        scheduler = self.scheduler(output)
        self.assertTrue(scheduler.pulse(CHANNELS, valid_until_ms=500))
        self.devices[17].fail.add('off')
        self.now = 350
        result = scheduler.tick()
        self.assertIsNone(result['outputs']['left'])
        self.assertFalse(result['outputs']['right'])
        self.assertIsNotNone(result['fault'])
        self.assertFalse(output.close())
        self.assertIn((17, 'close'), self.events)
        self.assertIn((27, 'close'), self.events)
        self.assertFalse(output.close())  # Idempotence retains a failed cleanup result.

    def test_close_failure_on_first_pin_still_releases_second(self):
        output = self.output()
        self.devices[17].fail.add('close')
        self.assertFalse(output.close())
        self.assertEqual(self.events[-2:], [(17, 'close'), (27, 'close')])
        with self.assertRaises(RuntimeError):
            output.write('right', True)

    def test_context_closes_scheduler_before_releasing_pins_on_caller_failure(self):
        with self.assertRaisesRegex(RuntimeError, 'Caller failure'):
            with self.output() as output:
                with HapticScheduler(output, clock=self.clock) as scheduler:
                    scheduler.set_ready(True)
                    self.now = 200
                    self.assertTrue(scheduler.pulse(CHANNELS, valid_until_ms=500))
                    raise RuntimeError('Caller failure')
        self.assertFalse(any(device.value for device in self.devices.values()))
        self.assertEqual(self.events[-4:], [(17, 'off'), (27, 'off'),
                                           (17, 'close'), (27, 'close')])

    def test_constructor_clock_failure_is_cleaned_by_outer_adapter(self):
        with self.assertRaises(RuntimeError):
            with self.output() as output:
                HapticScheduler(output, clock=lambda: float('nan'))
        self.assertEqual(self.events[-2:], [(17, 'close'), (27, 'close')])

    def test_expired_capture_and_guard_deadline_cannot_be_bypassed_by_adapter(self):
        output = self.output()
        scheduler = HapticScheduler(output, clock=self.clock)
        self.addCleanup(scheduler.close)
        scheduler.set_guard(lambda: 260)
        scheduler.set_ready(True)
        self.now = 200
        self.assertFalse(scheduler.pulse('left', valid_until_ms=200))
        self.assertTrue(scheduler.pulse(CHANNELS, 500, valid_until_ms=500))
        self.now = 260
        self.assertEqual(scheduler.tick()['outputs'], dict.fromkeys(CHANNELS, False))
        self.assertFalse(any(device.value for device in self.devices.values()))
        self.assertFalse(scheduler.set_ready(True))

    def test_bench_is_bounded_and_reports_command_state_without_hardware_acceptance(self):
        def sleep(seconds):
            self.now += seconds * 1000
        result = bench(self.output(), channels=CHANNELS, duration_ms=100,
                       clock=self.clock, sleep=sleep)
        self.assertEqual(result['accepted'], 1)
        self.assertEqual(result['outputs'], dict.fromkeys(CHANNELS, False))
        self.assertTrue(result['closed'])
        self.assertTrue(result['bench_only'])
        self.assertFalse(result['physical_acceptance'])

    def test_off_only_bench_never_arms_or_writes_high(self):
        result = bench(self.output(), clock=self.clock)
        self.assertEqual(result['accepted'], 0)
        self.assertNotIn('on', [action for _, action in self.events])


class CommandTests(unittest.TestCase):
    args = ['--enable-gpio', '--left-bcm', '17', '--right-bcm', '27', '--active-high', '--off-only']

    def test_no_opt_in_no_action_or_invalid_duration_never_constructs_adapter(self):
        for args in ([], self.args[1:], self.args[:-1],
                     self.args + ['--duration-ms', 'nan'],
                     self.args + ['--duration-ms', '501'],
                     self.args + ['--duration-ms', '0']):
            with self.subTest(args=args), patch('edge.haptic_gpio.GPIOOutput') as factory:
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main(args)
                factory.assert_not_called()

    def test_success_printed_only_after_adapter_cleanup_and_signal_restored(self):
        adapter = Mock()
        adapter.__enter__ = Mock(return_value=adapter)
        adapter.__exit__ = Mock(return_value=False)
        previous = signal.getsignal(signal.SIGTERM)
        stdout = io.StringIO()
        with patch('edge.haptic_gpio.GPIOOutput', return_value=adapter), \
                patch('edge.haptic_gpio.bench', return_value={'gpio_used': True}) as run, \
                redirect_stdout(stdout):
            self.assertEqual(main(self.args), 0)
        run.assert_called_once_with(adapter, channels=(), duration_ms=150)
        adapter.__exit__.assert_called_once()
        self.assertTrue(json.loads(stdout.getvalue())['adapter_closed'])
        self.assertEqual(signal.getsignal(signal.SIGTERM), previous)

    def test_bench_error_interrupt_and_cleanup_error_never_print_success(self):
        for failure, expected in ((RuntimeError('private details'), 1), (KeyboardInterrupt(), 130)):
            adapter = Mock()
            adapter.__enter__ = Mock(return_value=adapter)
            adapter.__exit__ = Mock(return_value=False)
            stdout = io.StringIO()
            with patch('edge.haptic_gpio.GPIOOutput', return_value=adapter), \
                    patch('edge.haptic_gpio.bench', side_effect=failure), redirect_stdout(stdout):
                self.assertEqual(main(self.args), expected)
            adapter.__exit__.assert_called_once()
            self.assertNotIn('private', stdout.getvalue())
            self.assertNotIn('adapter_closed', stdout.getvalue())


if __name__ == '__main__':
    unittest.main()
