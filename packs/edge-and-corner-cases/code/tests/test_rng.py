"""The generator's randomness is SplitMix64, pinned to published test vectors, so seeds reproduce anywhere."""

from __future__ import annotations

import unittest

from edge_cases.rng import MASK, SplitMix64, check_seed, derive


class SplitMix64Vectors(unittest.TestCase):
    def test_published_vectors(self) -> None:
        rng = SplitMix64(0)
        self.assertEqual([rng.next64() for _ in range(3)],
                         [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F])
        rng = SplitMix64(1234567)
        self.assertEqual([rng.next64() for _ in range(5)],
                         [6457827717110365317, 3203168211198807973, 9817491932198370423, 4593380528125082431,
                          16408922859458223821])

    def test_outputs_stay_in_64_bits(self) -> None:
        rng = SplitMix64(MASK)
        for _ in range(1000):
            self.assertTrue(0 <= rng.next64() <= MASK)


class Draws(unittest.TestCase):
    def test_below_and_between_stay_in_range_and_reach_both_ends(self) -> None:
        rng = SplitMix64(42)
        seen = {rng.between(-2, 2) for _ in range(500)}
        self.assertEqual(seen, {-2, -1, 0, 1, 2})
        self.assertTrue(all(0 <= rng.below(7) < 7 for _ in range(500)))

    def test_bad_arguments_fail_loudly(self) -> None:
        rng = SplitMix64(1)
        for call in (lambda: rng.below(0), lambda: rng.between(3, 2), lambda: rng.choice([])):
            with self.assertRaises(ValueError):
                call()
        for seed in (-1, MASK + 1, 1.5, True, "7"):
            with self.assertRaises(ValueError):
                check_seed(seed)

    def test_shuffle_keeps_every_item_and_leaves_the_input_alone(self) -> None:
        items = list(range(20)) + [3, 3]
        out = SplitMix64(9).shuffled(items)
        self.assertEqual(sorted(out), sorted(items))
        self.assertNotEqual(out, items)
        self.assertEqual(items, list(range(20)) + [3, 3])

    def test_same_seed_same_stream_and_streams_per_kind_differ(self) -> None:
        a, b = SplitMix64(derive(5, "dates")), SplitMix64(derive(5, "dates"))
        self.assertEqual([a.next64() for _ in range(4)], [b.next64() for _ in range(4)])
        self.assertNotEqual(derive(5, "dates"), derive(5, "lists"))
        self.assertNotEqual(derive(5, "dates"), derive(6, "dates"))


if __name__ == "__main__":
    unittest.main()
