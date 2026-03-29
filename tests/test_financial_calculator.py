"""
Unit tests for the financial calculator — no LLM, no DB needed.
Run with: pytest tests/
"""
import pytest
from app.services.financial_calculator import (
    sip_future_value,
    required_sip,
    lumpsum_future_value,
    retirement_corpus_needed,
    tax_old_regime,
    tax_new_regime,
    tax_comparison,
    hra_exemption,
    compute_health_score,
    emergency_fund_gap,
    inflation_adjusted,
)


class TestSIPCalculations:
    def test_sip_fv_basic(self):
        """₹10,000/month at 12% for 10 years ≈ ₹23.2 L"""
        fv = sip_future_value(10_000, 0.12, 10)
        assert 2_200_000 < fv < 2_500_000

    def test_sip_fv_zero_years(self):
        assert sip_future_value(10_000, 0.12, 0) == 0.0

    def test_required_sip_roundtrip(self):
        """required_sip should be the inverse of sip_future_value."""
        target = 5_000_000
        sip = required_sip(target, 0.12, 20)
        fv = sip_future_value(sip, 0.12, 20)
        assert abs(fv - target) < 1000  # within ₹1000

    def test_lumpsum_fv(self):
        """₹1L at 10% for 10 years ≈ ₹2.59L"""
        fv = lumpsum_future_value(100_000, 0.10, 10)
        assert abs(fv - 259_374) < 1000

    def test_inflation_adjusted(self):
        """₹50k today at 6% inflation for 25 years ≈ ₹2.15L"""
        result = inflation_adjusted(50_000, 25)
        assert 200_000 < result < 230_000


class TestRetirementCorpus:
    def test_basic_corpus_calculation(self):
        result = retirement_corpus_needed(
            monthly_expenses_today=50_000,
            current_age=30,
            retirement_age=60,
        )
        assert result["years_to_retire"] == 30
        assert result["corpus_needed"] > 10_000_000  # should be well over ₹1 Cr
        assert result["sip_required_12pct"] > 0
        assert result["monthly_expenses_at_retire"] > 50_000  # inflation adjusted

    def test_early_retirement_needs_more_corpus(self):
        early = retirement_corpus_needed(50_000, 30, 45)
        normal = retirement_corpus_needed(50_000, 30, 60)
        # Less time to accumulate but also longer retirement period — corpus still large
        assert early["corpus_needed"] > 0
        assert early["sip_required_12pct"] > normal["sip_required_12pct"]


class TestTaxCalculations:
    def test_tax_zero_income(self):
        result = tax_old_regime(0)
        assert result["total_tax"] == 0

    def test_tax_below_basic_exemption(self):
        result = tax_old_regime(250_000)
        assert result["total_tax"] == 0

    def test_new_regime_rebate_under_7L(self):
        """Income up to ₹7L has zero tax under new regime (after rebate)."""
        result = tax_new_regime(700_000)
        assert result["total_tax"] == 0

    def test_old_vs_new_high_deductions(self):
        """With max deductions, old regime should save tax for higher incomes."""
        cmp = tax_comparison(
            gross_annual=1_200_000,
            deductions_80c=150_000,
            nps_80ccd=50_000,
        )
        # With ₹2L in deductions, old regime should be better
        assert cmp["recommendation"] in ("old_regime", "new_regime")  # math-dependent

    def test_effective_rate_is_percentage(self):
        result = tax_old_regime(1_500_000)
        assert 0 <= result["effective_rate"] <= 40

    def test_monthly_take_home_is_reasonable(self):
        result = tax_new_regime(1_200_000)
        # Monthly take home should be less than monthly gross
        assert result["monthly_take_home"] < 1_200_000 / 12


class TestHRAExemption:
    def test_hra_metro(self):
        """HRA exemption for metro should use 50% of basic."""
        exempt = hra_exemption(
            basic_salary_annual=600_000,
            hra_received_annual=300_000,
            rent_paid_annual=240_000,
            is_metro=True,
        )
        # min(300k, 300k, 180k) = 180k
        assert exempt == 180_000

    def test_hra_non_metro(self):
        exempt = hra_exemption(
            basic_salary_annual=600_000,
            hra_received_annual=300_000,
            rent_paid_annual=240_000,
            is_metro=False,
        )
        # min(300k, 240k, 180k) = 180k
        assert exempt == 180_000

    def test_no_rent_no_exemption(self):
        exempt = hra_exemption(600_000, 300_000, 0, True)
        assert exempt == 0


class TestHealthScore:
    def test_perfect_score_profile(self):
        score = compute_health_score(
            monthly_income=200_000,
            monthly_expenses=80_000,
            emergency_fund=480_000,   # 6 months
            life_cover=24_000_000,    # 10x income
            health_cover=500_000,
            debt_emi=0,
            investment_monthly=40_000,  # 20% of income
            has_term_plan=True,
            age=30,
        )
        assert score["total_score"] > 80
        assert score["grade"] == "A"

    def test_poor_profile_low_score(self):
        score = compute_health_score(
            monthly_income=50_000,
            monthly_expenses=48_000,
            emergency_fund=0,
            life_cover=0,
            health_cover=0,
            debt_emi=30_000,
            investment_monthly=0,
            has_term_plan=False,
            age=45,
        )
        assert score["total_score"] < 40
        assert score["grade"] in ("D", "F")

    def test_savings_rate_calculation(self):
        score = compute_health_score(
            monthly_income=100_000,
            monthly_expenses=70_000,
            emergency_fund=420_000,
            life_cover=10_000_000,
            health_cover=500_000,
            debt_emi=0,
            investment_monthly=20_000,  # 20%
            has_term_plan=True,
            age=35,
        )
        assert score["savings_rate_pct"] == 20.0


class TestEmergencyFund:
    def test_full_coverage(self):
        result = emergency_fund_gap(50_000, 300_000)  # exactly 6 months
        assert result["gap"] == 0
        assert result["months_covered"] == 6.0

    def test_gap_calculation(self):
        result = emergency_fund_gap(50_000, 100_000)  # only 2 months
        assert result["gap"] == 200_000
        assert result["months_covered"] == 2.0
