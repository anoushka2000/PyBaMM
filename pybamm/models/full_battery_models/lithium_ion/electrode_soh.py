#
# A model to calculate electrode-specific SOH
#
import pybamm
import numpy as np


class ElectrodeSOH(pybamm.BaseModel):
    """Model to calculate electrode-specific SOH, from [1]_.
    This model is mainly for internal use, to calculate summary variables in a
    simulation.

    .. math::
        n_{Li} = \\frac{3600}{F}(y_{100}C_p + x_{100}C_n),
    .. math::
        V_{max} = U_p(y_{100}) - U_n(x_{100}),
    .. math::
        V_{min} = U_p(y_{0}) - U_n(x_{0}),
    .. math::
        x_0 = x_{100} - \\frac{C}{C_n},
    .. math::
        y_0 = y_{100} + \\frac{C}{C_p}.

    References
    ----------
    .. [1] Mohtat, P., Lee, S., Siegel, J. B., & Stefanopoulou, A. G. (2019). Towards
           better estimability of electrode-specific state of health: Decoding the cell
           expansion. Journal of Power Sources, 427, 101-111.

    **Extends:** :class:`pybamm.BaseModel`
    """

    def __init__(self, parameter_values, name="Electrode-specific SOH model"):
        pybamm.citations.register("Mohtat2019")
        super().__init__(name)
        # TODO: combine variables from first and second simulations in final solution
        self.initial_variables = pybamm.FuzzyDict({})
        # TODO: not pass in parameter values?
        self.parameter_values = parameter_values

        param = pybamm.LithiumIonParameters()

        Un = param.n.U_dimensional
        Up = param.p.U_dimensional
        T_ref = param.T_ref

        V_min = pybamm.InputParameter("V_min")
        Cn = pybamm.InputParameter("C_n")
        Cp = pybamm.InputParameter("C_p")
        n_Li = pybamm.InputParameter("n_Li")

        x_100 = pybamm.Variable("x_100")
        y_100 = (n_Li * param.F / 3600 - x_100 * Cn) / Cp

        y_100_min = 1e-10
        x_100_upper_limit = min(((n_Li * param.F) / 3600 - y_100_min * Cp) / Cn, 1 - 1e-10)

        # TODO: get input values to calculate these

        #         Vmax_init = self.parameter_values.evaluate(Up(y_100_min, T_ref)) - self.parameter_values.evaluate(Un(x_100_upper_limit,
        #                                                                                                    T_ref))
        #         Vmin_init = self.parameter_values.evaluate(Up(y_100_min + 1, T_ref)) - self.parameter_values.evaluate(
        #             Un(x_100_upper_limit - Cp / Cn, T_ref))

        #         if isinstance(self.parameter_values["Positive electrode OCP [V]"], tuple):
        #             y_100_min = np.min(self.parameter_values["Positive electrode OCP [V]"][1][1])
        #             x_100_upper_limit = (n_Li * pybamm.constants.F.value / 3600 - y_100_min * C_p) / C_n

        #             V_lower_bound = min(self.parameter_values["Positive electrode OCP [V]"][1][1]) - self.parameter_values[
        #                 "Negative electrode OCP [V]"](x_100_upper_limit).evaluate()
        #             V_upper_bound = max(self.parameter_values["Positive electrode OCP [V]"][1][1]) - self.parameter_values[
        #                 "Negative electrode OCP [V]"](x_100_upper_limit).evaluate()

        #             if Vmin_init[0][0] < V_lower_bound:
        #                 raise (ValueError(
        #                     "Initial values are outside bounds of OCP data in parameter set."))

        #             if Vmax_init[0][0] > V_upper_bound:
        #                 raise (ValueError(
        #                     "Initial values are outside bounds of OCP data in parameter set."))

        x_100, y_100 = self.solve_initial_state()

        C = pybamm.Variable("C")
        x_0 = x_100 - C / Cn
        y_0 = y_100 + C / Cp

        self.algebraic = {
            C: Up(y_0, T_ref) - Un(x_0, T_ref) - V_min
        }

        self.initial_conditions = {C: Cp}

        self.variables = {
            "C": C,
            "x_0": x_0,
            "y_0": y_0,
        }

    @property
    def default_solver(self):
        # Use AlgebraicSolver as CasadiAlgebraicSolver gives unnecessary warnings
        return pybamm.AlgebraicSolver()

    def solve_initial_state(self):
        model = pybamm.BaseModel()

        param = pybamm.LithiumIonParameters()

        Un = param.n.U_dimensional
        Up = param.p.U_dimensional
        T_ref = param.T_ref

        x_100 = pybamm.Variable("x_100")
        y_100 = (n_Li * param.F / 3600 - x_100 * Cn) / Cp

        model.algebraic = {
            x_100: Up(y_100, T_ref) - Un(x_100, T_ref) - Vmax + 1e5 * (y_100 < 0) + 1e5 * (x_100 > 1),
        }

        model.initial_conditions = {
            x_100: x_100_upper_limit
        }

        model.variables = {
            "x_100": x_100,
            "y_100": y_100
        }

        sim = pybamm.Simulation(model, parameter_values=self.parameter_values)

        inital_sol = sim.solve([0])

        x_100 = inital_sol["x_100"].data[0]
        y_100 = inital_sol["y_100"].data[0]

        self.initial_variables = inital_sol._variables

        return x_100, y_100


def get_initial_stoichiometries(initial_soc, parameter_values):
    """
    Calculate initial stoichiometries to start off the simulation at a particular
    state of charge, given voltage limits, open-circuit potentials, etc defined by
    parameter_values

    Parameters
    ----------
    initial_soc : float
        Target initial SOC. Must be between 0 and 1.
    parameter_values : :class:`pybamm.ParameterValues`
        The parameter values class that will be used for the simulation. Required for
        calculating appropriate initial stoichiometries.

    Returns
    -------
    x, y
        The initial stoichiometries that give the desired initial state of charge
    """
    if initial_soc < 0 or initial_soc > 1:
        raise ValueError("Initial SOC should be between 0 and 1")

    model = pybamm.lithium_ion.ElectrodeSOH()

    param = pybamm.LithiumIonParameters()
    sim = pybamm.Simulation(model, parameter_values=parameter_values)

    V_min = parameter_values.evaluate(param.voltage_low_cut_dimensional)
    V_max = parameter_values.evaluate(param.voltage_high_cut_dimensional)
    C_n = parameter_values.evaluate(param.C_n_init)
    C_p = parameter_values.evaluate(param.C_p_init)
    n_Li = parameter_values.evaluate(param.n_Li_particles_init)

    # Solve the model and check outputs
    sol = sim.solve(
        [0],
        inputs={
            "V_min": V_min,
            "V_max": V_max,
            "C_n": C_n,
            "C_p": C_p,
            "n_Li": n_Li,
        },
    )

    x_0 = sol["x_0"].data[0]
    y_0 = sol["y_0"].data[0]
    C = sol["C"].data[0]
    x = x_0 + initial_soc * C / C_n
    y = y_0 - initial_soc * C / C_p

    return x, y
