#
# Test base electrolyte conductivity submodel
#

import pybamm
import tests
import unittest


class TestBaseElectrolyteConductivity(unittest.TestCase):
    def test_public_functions(self):
        submodel = pybamm.electrolyte.BaseElectrolyteConductivity(None)
        std_tests = tests.StandardSubModelTests(submodel)
        std_tests.test_all()


if __name__ == "__main__":
    print("Add -v for more debug output")
    import sys

    if "-v" in sys.argv:
        debug = True
    unittest.main()
