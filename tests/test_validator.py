"""Tests for the site validator detection helpers (unit-level, no browser)."""

from mm2hunter.scraper.validator import (
    STRIPE_HTML_INDICATORS,
    SiteValidator,
    ValidationResult,
    _check_harvester_fast,
    _detect_stripe_fast,
    _detect_wallet_fast,
)

# ---------------------------------------------------------------------------
# Fast stripe detection (pre-compiled combined regex)
# ---------------------------------------------------------------------------

def _detect_stripe_html(html_lower: str) -> bool:
    """Check HTML string indicators only (mirrors the old _detect_stripe)."""
    return any(ind.lower() in html_lower for ind in STRIPE_HTML_INDICATORS)


def test_stripe_detection_positive():
    html = '<script src="https://js.stripe.com/v3/"></script>'
    assert _detect_stripe_html(html.lower()) is True


def test_stripe_detection_powered_by():
    html = '<footer>Powered by Stripe</footer>'
    assert _detect_stripe_html(html.lower()) is True


def test_stripe_detection_negative():
    html = '<footer>Powered by PayPal</footer>'
    assert _detect_stripe_html(html.lower()) is False


def test_stripe_detection_pk_live():
    html = '<script>var key = "pk_live_abc123def456";</script>'
    assert _detect_stripe_html(html.lower()) is True


def test_stripe_detection_checkout_url():
    html = '<a href="https://checkout.stripe.com/pay/cs_test_abc">Pay</a>'
    assert _detect_stripe_html(html.lower()) is True


def test_stripe_detection_api_url():
    html = '<meta content="https://api.stripe.com" />'
    assert _detect_stripe_html(html.lower()) is True


def test_stripe_detection_data_attribute():
    html = '<div data-stripe="true">payment</div>'
    assert _detect_stripe_html(html.lower()) is True


def test_stripe_detection_stripe_element_class():
    html = '<div class="StripeElement">card input</div>'
    detected, _ = _detect_stripe_fast(html.lower())
    assert detected is True


def test_stripe_detection_load_stripe_js():
    html = '<script>const stripe = await loadStripe("pk_test_123");</script>'
    detected, evidence = _detect_stripe_fast(html.lower())
    assert detected is True
    assert any("script:" in e for e in evidence)


def test_stripe_detection_confirm_payment():
    html = '<script>stripe.confirmCardPayment(clientSecret);</script>'
    detected, evidence = _detect_stripe_fast(html.lower())
    assert detected is True


def test_stripe_detection_payment_intent():
    html = '<script>var x = "payment_intent_abc123";</script>'
    detected, evidence = _detect_stripe_fast(html.lower())
    assert detected is True


def test_stripe_fast_negative():
    html = '<html><body>Just a normal page</body></html>'
    detected, evidence = _detect_stripe_fast(html.lower())
    assert detected is False
    assert evidence == []


# ---------------------------------------------------------------------------
# Wallet detection (pre-compiled combined regex)
# ---------------------------------------------------------------------------

def test_wallet_detection_add_funds():
    html = '<a href="/wallet">Add Funds</a>'
    assert _detect_wallet_fast(html.lower()) is True


def test_wallet_detection_balance():
    html = '<span class="user-balance">Balance: $0.00</span>'
    assert _detect_wallet_fast(html.lower()) is True


def test_wallet_detection_negative():
    html = '<span>Welcome to our shop</span>'
    assert _detect_wallet_fast(html.lower()) is False


def test_wallet_detection_top_up():
    html = '<button>Top Up Account</button>'
    assert _detect_wallet_fast(html.lower()) is True


def test_wallet_detection_deposit():
    html = '<a href="/deposit">Deposit Now</a>'
    assert _detect_wallet_fast(html.lower()) is True


def test_wallet_static_method():
    html = '<a href="/wallet">Add Funds</a>'
    assert SiteValidator._detect_wallet(html.lower()) is True


def test_wallet_static_method_negative():
    html = '<span>No wallet here</span>'
    # "wallet" is in the text so this should be True
    assert SiteValidator._detect_wallet(html.lower()) is True


def test_wallet_static_really_negative():
    html = '<span>Welcome to the shop</span>'
    assert SiteValidator._detect_wallet(html.lower()) is False


# ---------------------------------------------------------------------------
# Harvester detection (fast, pre-compiled)
# ---------------------------------------------------------------------------

def test_harvester_found():
    html = '<div class="product">Harvester - $4.50 - In Stock</div>'
    found, in_stock, price = _check_harvester_fast(html.lower())
    assert found is True
    assert in_stock is True
    assert price == 4.50


def test_harvester_not_found():
    html = '<div class="product">Godly Knife - $10.00</div>'
    found, _, _ = _check_harvester_fast(html.lower())
    assert found is False


def test_harvester_out_of_stock():
    html = '<div>Harvester - $5.00 - Out of Stock</div>'
    found, in_stock, price = _check_harvester_fast(html.lower())
    assert found is True
    assert in_stock is False
    assert price == 5.00


def test_harvester_price_extraction():
    html = '<div>Harvester</div><span class="price">$3.99</span>'
    found, _, price = _check_harvester_fast(html.lower())
    assert found is True
    assert price == 3.99


def test_harvester_multiple_prices():
    html = '<div>Harvester $12.00 $5.50 $3.00</div>'
    found, _, price = _check_harvester_fast(html.lower())
    assert found is True
    assert price == 3.00


def test_harvester_sold_out():
    html = '<div>Harvester $4.00 Sold Out</div>'
    found, in_stock, price = _check_harvester_fast(html.lower())
    assert found is True
    assert in_stock is False
    assert price == 4.00


def test_harvester_buy_now_in_stock():
    html = '<div>Harvester $5.00</div><button>Buy Now</button>'
    found, in_stock, price = _check_harvester_fast(html.lower())
    assert found is True
    assert in_stock is True
    assert price == 5.00


def test_harvester_no_price():
    html = '<div>Harvester item available</div><button>Buy Now</button>'
    found, in_stock, price = _check_harvester_fast(html.lower())
    assert found is True
    assert in_stock is True
    assert price is None


# ---------------------------------------------------------------------------
# ValidationResult model
# ---------------------------------------------------------------------------

def test_validation_result_to_dict():
    r = ValidationResult(
        url="https://shop.example.com",
        has_stripe=True,
        has_wallet=True,
        harvester_found=True,
        harvester_in_stock=True,
        harvester_price=4.50,
        passed=True,
        scan_mode="fast",
    )
    d = r.to_dict()
    assert d["url"] == "https://shop.example.com"
    assert d["passed"] is True
    assert d["scan_mode"] == "fast"
    assert "discovered_at" in d


def test_validation_result_defaults():
    r = ValidationResult(url="https://test.com")
    assert r.has_stripe is False
    assert r.passed is False
    assert r.scan_mode == "fast"
    assert r.error is None


def test_validation_result_deep_mode():
    r = ValidationResult(url="https://test.com", scan_mode="deep")
    assert r.scan_mode == "deep"
    d = r.to_dict()
    assert d["scan_mode"] == "deep"
