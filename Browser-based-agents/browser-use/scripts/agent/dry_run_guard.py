"""
A hard, code-level guarantee that a browser session cannot actually submit
anything — for testing/dry-run scenarios where prompt-only "don't submit"
instructions to the LLM agent are not good enough on their own.

Why this exists: prompt instructions telling browser-use's agent not to
click submit have repeatedly been circumvented in practice — once via a JS
`evaluate` call doing `.click()` on the submit button instead of the click
action, and once via a direct click contradicting the agent's own stated
plan to stop. Both happened on a real, live registration page. Relying on
the LLM to police itself is not sufficient when the cost of it getting that
wrong is an actual registration going through.

This module blocks submission at the DOM-API / network level instead, so it
holds regardless of how the agent (or the page's own JS) tries to trigger
it: a native <form> submit (click, Enter key, .submit(), .requestSubmit()),
a React/SPA-style fetch()/XMLHttpRequest POST (the likely mechanism for a
page like Luma's, where the "Request to Join" button isn't a real form
submit), or navigator.sendBeacon.

Usage:
    from agent.dry_run_guard import install_never_submit_guard, get_blocked_submit_attempts

    browser = Browser(browser_profile=BrowserProfile(headless=True))
    await install_never_submit_guard(browser)   # BEFORE the Agent ever navigates
    ... run the Agent as normal ...
    blocked = await get_blocked_submit_attempts(browser)  # ground truth, not the agent's self-report
"""

# Injected via CDP Page.addScriptToEvaluateOnNewDocument (runImmediately=True),
# so it's in place before the current page's own scripts run, and is
# re-injected automatically on every subsequent navigation/reload too.
_NEVER_SUBMIT_SCRIPT = r"""
(() => {
  if (window.__NEVER_SUBMIT_INSTALLED__) return;
  window.__NEVER_SUBMIT_INSTALLED__ = true;
  window.__BLOCKED_SUBMIT_ATTEMPTS__ = [];

  function record(kind, detail) {
    try {
      window.__BLOCKED_SUBMIT_ATTEMPTS__.push({
        kind: kind,
        detail: String(detail == null ? '' : detail).slice(0, 500),
        t: Date.now(),
      });
    } catch (e) {}
  }

  // 1. Native <form> submission, however triggered (click on submit button,
  //    Enter key, form.submit(), form.requestSubmit()).
  document.addEventListener('submit', function (e) {
    record('form-submit-event', e.target && e.target.action);
    e.preventDefault();
    e.stopImmediatePropagation();
  }, true);

  HTMLFormElement.prototype.submit = function () {
    record('form.submit()', this.action);
  };
  if (HTMLFormElement.prototype.requestSubmit) {
    HTMLFormElement.prototype.requestSubmit = function () {
      record('form.requestSubmit()', this.action);
    };
  }

  // 2. fetch()-based submission (the likely path for SPA registration
  //    flows, e.g. Luma, where a button's onClick handler POSTs directly
  //    rather than using a real <form> submit).
  var origFetch = window.fetch;
  window.fetch = function (input, init) {
    var method = ((init && init.method) || (input && input.method) || 'GET').toUpperCase();
    if (method !== 'GET' && method !== 'HEAD') {
      var url = typeof input === 'string' ? input : (input && input.url);
      record('fetch-' + method, url);
      return Promise.resolve(new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }));
    }
    return origFetch.apply(this, arguments);
  };

  // 3. XMLHttpRequest-based submission.
  var origOpen = XMLHttpRequest.prototype.open;
  var origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url) {
    this.__blocked_submit__ = method && !/^(GET|HEAD)$/i.test(method);
    this.__method__ = method;
    this.__url__ = url;
    return origOpen.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function () {
    if (this.__blocked_submit__) {
      record('xhr-' + this.__method__, this.__url__);
      var self = this;
      setTimeout(function () {
        Object.defineProperty(self, 'readyState', { value: 4, configurable: true });
        Object.defineProperty(self, 'status', { value: 200, configurable: true });
        Object.defineProperty(self, 'responseText', { value: '{}', configurable: true });
        self.dispatchEvent(new Event('readystatechange'));
        self.dispatchEvent(new Event('load'));
      }, 0);
      return;
    }
    return origSend.apply(this, arguments);
  };

  // 4. navigator.sendBeacon (occasionally used for "fire and forget" submits).
  if (navigator.sendBeacon) {
    navigator.sendBeacon = function (url) {
      record('sendBeacon', url);
      return true;
    };
  }
})();
"""


async def install_never_submit_guard(browser) -> None:
    """
    Install the guard on `browser` (a browser_use.Browser/BrowserSession).
    Call this BEFORE the Agent navigates anywhere — it needs to be present
    from the first page load to guarantee coverage.
    """
    await browser._cdp_add_init_script(_NEVER_SUBMIT_SCRIPT)
    # runImmediately also arms it on whatever page is currently loaded (e.g.
    # about:blank at startup), but if a page was already navigated before
    # this call, arm it directly too as a belt-and-suspenders measure.
    try:
        page = await browser.get_current_page()
        await page.evaluate(_NEVER_SUBMIT_SCRIPT)
    except Exception:
        pass


async def get_blocked_submit_attempts(browser) -> list[dict]:
    """
    Ground truth: every submission attempt the guard actually blocked, in
    order. Empty list means nothing ever tried to submit — trust this over
    the agent's own self-reported claims about whether it submitted.
    """
    page = await browser.get_current_page()
    try:
        return await page.evaluate("() => window.__BLOCKED_SUBMIT_ATTEMPTS__ || []")
    except Exception:
        return []
