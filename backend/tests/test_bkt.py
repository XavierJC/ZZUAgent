import pytest

from eduagent.domain.bkt import BKTParameters, update_bkt


@pytest.mark.parametrize("correct,posterior,next_mastery", [
    (True, 9 / 19, 10 / 19),
    (False, 1 / 31, 4 / 31),
])
def test_hand_calculated_first_observation(correct, posterior, next_mastery):
    result = update_bkt(0.2, correct, BKTParameters())
    assert result.prior == 0.2
    assert result.posterior == pytest.approx(posterior)
    assert result.next_mastery == pytest.approx(next_mastery)


def test_two_successes_match_independent_reference():
    first = update_bkt(0.2, True, BKTParameters())
    second = update_bkt(first.next_mastery, True, BKTParameters())
    assert second.posterior == pytest.approx(0.8)
    assert second.next_mastery == pytest.approx(0.82)


@pytest.mark.parametrize("prior", [0.01, 0.2, 0.5, 0.99])
def test_informative_observation_and_no_forgetting(prior):
    right = update_bkt(prior, True, BKTParameters())
    wrong = update_bkt(prior, False, BKTParameters())
    assert right.posterior > prior > wrong.posterior
    for result in (right, wrong):
        assert 0 <= result.posterior <= result.next_mastery <= 1


def test_wrong_answer_final_state_can_increase_due_to_learning():
    result = update_bkt(0.2, False, BKTParameters(learn=0.9))
    assert result.posterior < result.prior < result.next_mastery


@pytest.mark.parametrize("prior,expected", [(0.0, 0.1), (1.0, 1.0)])
@pytest.mark.parametrize("correct", [True, False])
def test_prior_boundaries(prior, expected, correct):
    assert update_bkt(prior, correct, BKTParameters()).next_mastery == pytest.approx(expected)


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf"), True, "0.2"])
def test_invalid_probabilities(value):
    with pytest.raises(ValueError):
        BKTParameters(initial=value)
    with pytest.raises(ValueError):
        update_bkt(value, True, BKTParameters())


@pytest.mark.parametrize("field", ["learn", "slip", "guess"])
def test_each_parameter_is_validated(field):
    with pytest.raises(ValueError):
        BKTParameters(**{field: -0.01})


@pytest.mark.parametrize("prior,correct,parameters", [
    (0.0, True, BKTParameters(guess=0)),
    (1.0, False, BKTParameters(slip=0)),
])
def test_impossible_observations_raise(prior, correct, parameters):
    with pytest.raises(ValueError, match="观测概率为零"):
        update_bkt(prior, correct, parameters)


def test_correct_flag_is_not_coerced():
    with pytest.raises(ValueError, match="布尔"):
        update_bkt(0.2, 1, BKTParameters())
