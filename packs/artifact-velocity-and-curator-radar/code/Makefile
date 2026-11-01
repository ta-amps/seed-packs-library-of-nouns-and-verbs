.PHONY: check test self-test

check: test self-test

test:
	python3 -m unittest discover -s tests -p "test_*.py" -v

self-test:
	python3 -m velocity_signal_radar --self-test
