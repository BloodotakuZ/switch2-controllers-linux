"""BLE report -> virtual input regressions; no Bluetooth/uinput device needed."""
import unittest
from unittest.mock import patch

from evdev import ecodes as e
from ngc import protocol as P
from ngc.gamepad import SwitchGamepad, button_map_for_product
from tools.sdl_guid import fix_pro_mapping, mapping_for_pad


class ProButtonsTest(unittest.TestCase):
    def setUp(self):
        with patch('ngc.gamepad.UInput') as ui, patch('ngc.gamepad.threading.Thread'):
            self.pad = SwitchGamepad(
                product=P.PRO_CONTROLLER2_PID,
                button_map=button_map_for_product(P.PRO_CONTROLLER2_PID),
            )
            self.keys = ui.call_args.args[0][e.EV_KEY]
        self.pad.update(0, (0, 0), (0, 0), 0, 0)
        self.pad.ui.reset_mock()

    def send(self, raw_mask):
        raw = bytearray(63)
        raw[4:8] = raw_mask.to_bytes(4, 'little')
        report = P.InputReport.parse(raw)
        self.pad.update(report.buttons, (0, 0), (0, 0), 0, 0)

    def test_physical_x_y_swapped(self):
        self.send(0x02)  # physical X
        self.pad.ui.write.assert_called_once_with(e.EV_KEY, e.BTN_NORTH, 1)
        self.pad.ui.reset_mock()
        self.send(0x01)  # release X, press Y
        self.pad.ui.write.assert_any_call(e.EV_KEY, e.BTN_NORTH, 0)
        self.pad.ui.write.assert_any_call(e.EV_KEY, e.BTN_WEST, 1)

    def test_extra_buttons_are_independent_and_release(self):
        expected = {
            0x02000000: e.BTN_TRIGGER_HAPPY1,  # GL
            0x01000000: e.BTN_TRIGGER_HAPPY2,  # GR
            0x00004000: e.BTN_C,
            0x00002000: e.BTN_Z,
        }
        for mask, code in expected.items():
            with self.subTest(mask=mask):
                self.pad.ui.reset_mock()
                self.send(mask)
                self.assertIn(code, self.keys)
                self.pad.ui.write.assert_called_once_with(e.EV_KEY, code, 1)
                self.pad.ui.reset_mock()
                self.send(0)
                self.pad.ui.write.assert_called_once_with(e.EV_KEY, code, 0)
        self.send(sum(expected))
        for code in expected.values():
            self.assertEqual(self.pad._last_keys[code], 1)
        self.pad.ui.reset_mock()
        self.pad.release_all()
        for code in expected.values():
            self.pad.ui.write.assert_any_call(e.EV_KEY, code, 0)

    def test_other_product_layouts_preserved(self):
        for pid in (P.JOYCON2_LEFT_PID, P.JOYCON2_RIGHT_PID):
            mapping = button_map_for_product(pid)
            self.assertEqual(mapping['X'], e.BTN_WEST)
            self.assertEqual(mapping['Y'], e.BTN_NORTH)
            self.assertNotIn('GL', mapping)
            self.assertNotIn('GR', mapping)
        gc = button_map_for_product(P.NSO_GAMECUBE_PID)
        self.assertEqual(gc['X'], e.BTN_NORTH)
        self.assertEqual(gc['Y'], e.BTN_WEST)
        self.assertEqual(gc['C'], e.BTN_SELECT)
        self.assertNotIn('GL', gc)

    def test_steam_elite_identity_and_paddle_events(self):
        with patch('ngc.gamepad.UInput') as ui, patch('ngc.gamepad.threading.Thread'):
            pad = SwitchGamepad(name='Pro Controller 2 (P1)',
                                product=P.PRO_CONTROLLER2_PID, steam_elite=True)
            caps = ui.call_args.args[0]
            identity = ui.call_args.kwargs
        self.assertEqual((identity['vendor'], identity['product'], identity['bustype']),
                         (0x045e, 0x0b00, e.BUS_USB))
        self.assertIn('[Steam Elite]', identity['name'])
        self.assertEqual(pad.button_map['X'], e.BTN_NORTH)
        self.assertEqual(pad.button_map['Y'], e.BTN_WEST)
        pad.update(0, (0, 0), (0, 0), 0, 0)
        pad.ui.reset_mock()
        pad.update(0x03000000, (0, 0), (0, 0), 0, 0)
        pad.ui.write.assert_any_call(e.EV_KEY, e.BTN_TRIGGER_HAPPY5, 1)
        pad.ui.write.assert_any_call(e.EV_KEY, e.BTN_TRIGGER_HAPPY7, 1)
        self.assertEqual(pad.ui.write.call_count, 2)
        pad.ui.reset_mock()
        pad.update(0, (0, 0), (0, 0), 0, 0)
        pad.ui.write.assert_any_call(e.EV_KEY, e.BTN_TRIGGER_HAPPY5, 0)
        pad.ui.write.assert_any_call(e.EV_KEY, e.BTN_TRIGGER_HAPPY7, 0)
        fields = dict(x.split(':', 1) for x in fix_pro_mapping(
            'guid,Pro Controller 2 (P1) [Steam Elite],dpup:h0.1,'
        ).split(',')[2:] if ':' in x)
        keys = caps[e.EV_KEY]
        self.assertEqual(fields['paddle1'], f'b{keys.index(e.BTN_TRIGGER_HAPPY5)}')
        self.assertEqual(fields['paddle2'], f'b{keys.index(e.BTN_TRIGGER_HAPPY7)}')

    def test_elite_mode_does_not_change_other_products(self):
        for pid in (P.NSO_GAMECUBE_PID, P.JOYCON2_LEFT_PID, P.JOYCON2_RIGHT_PID):
            with patch('ngc.gamepad.UInput') as ui, patch('ngc.gamepad.threading.Thread'):
                pad = SwitchGamepad(product=pid, steam_elite=True)
                identity = ui.call_args.kwargs
            self.assertEqual(identity['vendor'], P.NINTENDO_VENDOR_ID)
            self.assertEqual(identity['product'], pid)
            self.assertEqual(identity['bustype'], e.BUS_BLUETOOTH)
            self.assertNotIn('GL', pad.button_map)

    def test_sdl_mapping_matches_actual_key_and_axis_order(self):
        mapping = fix_pro_mapping('guid,Pro Controller 2,dpup:h0.1,')
        fields = dict(x.split(':', 1) for x in mapping.split(',')[2:] if ':' in x)
        for slot, code in {
            'x': e.BTN_WEST, 'y': e.BTN_NORTH,
            'misc1': e.BTN_C, 'misc2': e.BTN_Z,
            'paddle1': e.BTN_TRIGGER_HAPPY2, 'paddle2': e.BTN_TRIGGER_HAPPY1,
            'back': e.BTN_SELECT, 'start': e.BTN_START, 'guide': e.BTN_MODE,
            'leftstick': e.BTN_THUMBL, 'rightstick': e.BTN_THUMBR,
        }.items():
            self.assertEqual(fields[slot], f'b{self.keys.index(code)}')
        axes = sorted((e.ABS_X, e.ABS_Y, e.ABS_Z, e.ABS_RX, e.ABS_RY, e.ABS_RZ))
        for slot, code in {'rightx': e.ABS_RX, 'righty': e.ABS_RY,
                           'lefttrigger': e.ABS_Z, 'righttrigger': e.ABS_RZ}.items():
            self.assertEqual(fields[slot], f'a{axes.index(code)}')
        self.assertEqual(fields['dpup'], 'h0.1')
        self.assertNotIn('paddle1:', mapping_for_pad('Joy-Con 2 (Right)', 'guid,Joy-Con 2,'))


if __name__ == '__main__':
    unittest.main()
