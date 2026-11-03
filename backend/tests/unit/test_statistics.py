import statistics

import pytest

from app.services.statistics import benjamini_hochberg, linear_fit, pearson, t_test_p_value


def test_linear_fit_finds_slope_and_intercept():
    fit = linear_fit([2000, 2001, 2002, 2003], [10, 12, 14, 16])
    assert fit is not None
    assert fit.slope == pytest.approx(2)
    assert fit.at(2004) == pytest.approx(18)


def test_linear_fit_needs_three_points_and_variation():
    assert linear_fit([1, 2], [1, 2]) is None
    assert linear_fit([1, 1, 1], [1, 2, 3]) is None


def test_t_test_p_value_matches_reference_table():
    # r = 0,5 com 20 pares: t = 2,449 com 18 graus de liberdade, p bilateral = 0,0248
    assert t_test_p_value(2.449, 18) == pytest.approx(0.0248, abs=0.0005)
    assert t_test_p_value(0, 10) == pytest.approx(1)


def test_pearson_with_p_value():
    xs, ys = [1, 2, 3, 4, 5, 6, 7, 8], [2, 4, 5, 4, 5, 7, 8, 9]
    result = pearson(xs, ys)
    assert result is not None
    assert result.r == pytest.approx(statistics.correlation(xs, ys))
    assert result.p < 0.01
    assert result.n == 8


def test_pearson_without_variation_or_few_points():
    assert pearson([1, 2, 3], [1, 2, 3]) is None
    assert pearson([1, 2, 3, 4], [5, 5, 5, 5]) is None


def test_benjamini_hochberg():
    assert benjamini_hochberg([0.01, 0.04, 0.03, 0.005]) == pytest.approx([0.02, 0.04, 0.04, 0.02])
    assert benjamini_hochberg([]) == []
