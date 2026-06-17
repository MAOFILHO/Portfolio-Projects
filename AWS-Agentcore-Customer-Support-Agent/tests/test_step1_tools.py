"""Unit tests for Step 1 tool functions (no AWS calls required)."""
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# Import just the pure functions; skip AWS-dependent ones
from agentcore.step1_agent import get_return_policy, get_product_info, web_search


class TestGetReturnPolicy:
    def test_smartphone_policy(self):
        result = get_return_policy.__wrapped__("smartphones")
        assert "30 days" in result
        assert "Return Policy" in result

    def test_laptop_policy(self):
        result = get_return_policy.__wrapped__("laptops")
        assert "30 days" in result
        assert "Laptops" in result

    def test_accessories_policy(self):
        result = get_return_policy.__wrapped__("accessories")
        assert "30 days" in result
        assert "90-day manufacturer warranty" in result

    def test_case_insensitive(self):
        result_lower = get_return_policy.__wrapped__("laptops")
        result_upper = get_return_policy.__wrapped__("LAPTOPS")
        assert result_lower == result_upper

    def test_unknown_category_returns_default(self):
        result = get_return_policy.__wrapped__("drones")
        assert "30 days" in result
        assert "Contact technical support" in result


class TestGetProductInfo:
    def test_laptops(self):
        result = get_product_info.__wrapped__("laptops")
        assert "Laptops" in result
        assert "warranty" in result.lower()

    def test_smartphones(self):
        result = get_product_info.__wrapped__("smartphones")
        assert "Smartphones" in result
        assert "5G" in result

    def test_headphones(self):
        result = get_product_info.__wrapped__("headphones")
        assert "noise cancellation" in result.lower()

    def test_monitors(self):
        result = get_product_info.__wrapped__("monitors")
        assert "3-year" in result

    def test_unknown_product(self):
        result = get_product_info.__wrapped__("toaster")
        assert "not available" in result.lower()

    def test_case_insensitive(self):
        result = get_product_info.__wrapped__("LAPTOPS")
        assert "Laptops" in result


class TestWebSearch:
    def test_returns_string(self):
        # Just verify it returns a string without raising (may hit rate limit)
        result = web_search.__wrapped__("laptop overheating fix", max_results=1)
        assert isinstance(result, str)
