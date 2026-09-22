// Gate 0 executed pre-check.
//
// Runs the EA's OWN entry-path source text (lifted from the .mq5 between the
// XPDIR_GATE0_CORE markers) over EVERY combination of mode, hold-candidate
// state, crossings and ladder direction, and compares it against the literal
// 1.03 conditions:
//
//     BUY  block runs  <=>  buyHoldActive  || (!active && buyCrossing)
//     SELL block runs  <=>  sellHoldActive || (!active && sellCrossing)
//
// In DIR_OFF the two must agree on all 96 states, and no XPDir function may
// write a virtual stop level, reset the hold candidate, touch the CSV, or even
// ask the ladder for a direction. That is what "DIR_OFF reproduces 1.03" means
// at the level of code; the Strategy Tester proves it at the level of trades.
//
// It also asserts the modes that SHOULD differ actually do, so a build that
// silently no-ops DIR_LOCK or DIR_TRANSLATE fails here too.
#include "gate0_stubs.h"
#include "g0core.cpp"

static int failures = 0;
static int checks = 0;

static void CHECK(bool cond, const char* what, int mode, int a, int b, int c, int d, int e) {
  checks++;
  if (cond) return;
  failures++;
  printf("  FAIL %s  mode=%d active=%d isBuy=%d buyX=%d sellX=%d dir=%d\n",
         what, mode, a, b, c, d, e);
}

int main() {
  const ENUM_XPDIR_MODE modes[4] = { DIR_OFF, DIR_LOCK, DIR_TRANSLATE, DIR_VETO };
  const ENUM_XPDIR dirs[3] = { XPDIR_NONE, XPDIR_BUY, XPDIR_SELL };

  int offDiffers = 0, lockActed = 0, translateActed = 0, translateFlipped = 0;
  int vetoBlocked = 0, vetoAllowed = 0;

  for (int m = 0; m < 4; m++)
  for (int active = 0; active < 2; active++)
  for (int isBuy = 0; isBuy < 2; isBuy++)
  for (int buyX = 0; buyX < 2; buyX++)
  for (int sellX = 0; sellX < 2; sellX++)
  for (int di = 0; di < 3; di++) {
    StubReset();
    InpDirMode = modes[m];
    g_stubDir = dirs[di];
    g_EntryHoldCandidate.active = (active != 0);
    g_EntryHoldCandidate.isBuy = (isBuy != 0);

    const bool buyHoldActive  = g_EntryHoldCandidate.active &&  g_EntryHoldCandidate.isBuy;
    const bool sellHoldActive = g_EntryHoldCandidate.active && !g_EntryHoldCandidate.isBuy;

    // the literal 1.03 conditions
    const bool ref_buy  = buyHoldActive  || (!g_EntryHoldCandidate.active && buyX);
    const bool ref_sell = sellHoldActive || (!g_EntryHoldCandidate.active && sellX);

    const bool got_buy  = XPDir_BuyBlockRuns(buyHoldActive, buyX != 0, sellX != 0);
    const bool got_sell = XPDir_SellBlockRuns(sellHoldActive, buyX != 0, sellX != 0);

    if (modes[m] == DIR_OFF) {
      CHECK(got_buy == ref_buy,  "BuyBlockRuns != 1.03", m, active, isBuy, buyX, sellX, di);
      CHECK(got_sell == ref_sell, "SellBlockRuns != 1.03", m, active, isBuy, buyX, sellX, di);
      CHECK(g_stubDirCalls == 0, "DIR_OFF asked the ladder for a direction",
            m, active, isBuy, buyX, sellX, di);

      // no XPDir entry point may touch state in DIR_OFF
      g_VirtualBuyStopPrice = 111.0;
      g_VirtualSellStopPrice = 222.0;
      const int resets0 = g_stubResetCalls, csv0 = g_stubCsvCalls;
      XPDir_ApplyArmingLock();
      XPDir_NoteTrigger(buyX != 0, sellX != 0);
      XPDir_ClearTriggerLevels();
      CHECK(g_VirtualBuyStopPrice == 111.0 && g_VirtualSellStopPrice == 222.0,
            "DIR_OFF wrote a virtual stop level", m, active, isBuy, buyX, sellX, di);
      CHECK(g_stubResetCalls == resets0, "DIR_OFF reset the hold candidate",
            m, active, isBuy, buyX, sellX, di);
      CHECK(g_stubCsvCalls == csv0, "DIR_OFF wrote a CSV row", m, active, isBuy, buyX, sellX, di);
      CHECK(g_stubDirCalls == 0, "DIR_OFF asked the ladder for a direction (wiring)",
            m, active, isBuy, buyX, sellX, di);
      if (got_buy != ref_buy || got_sell != ref_sell) offDiffers++;
    } else {
      // DIR_LOCK must keep the 1.03 predicates and act only on the levels
      if (modes[m] == DIR_LOCK) {
        CHECK(got_buy == ref_buy,  "DIR_LOCK changed BuyBlockRuns", m, active, isBuy, buyX, sellX, di);
        CHECK(got_sell == ref_sell, "DIR_LOCK changed SellBlockRuns", m, active, isBuy, buyX, sellX, di);
        g_VirtualBuyStopPrice = 111.0; g_VirtualSellStopPrice = 222.0;
        XPDir_ApplyArmingLock();
        if (dirs[di] == XPDIR_BUY)
          CHECK(g_VirtualBuyStopPrice == 111.0 && g_VirtualSellStopPrice == 0.0,
                "DIR_LOCK BUY did not disarm the sell level", m, active, isBuy, buyX, sellX, di);
        else if (dirs[di] == XPDIR_SELL)
          CHECK(g_VirtualSellStopPrice == 222.0 && g_VirtualBuyStopPrice == 0.0,
                "DIR_LOCK SELL did not disarm the buy level", m, active, isBuy, buyX, sellX, di);
        else
          CHECK(g_VirtualBuyStopPrice == 0.0 && g_VirtualSellStopPrice == 0.0,
                "DIR_LOCK NONE left a level armed", m, active, isBuy, buyX, sellX, di);
        lockActed++;
      } else if (modes[m] == DIR_VETO) {
        // DIR_VETO: the host keeps its trigger AND its side. The ladder may
        // only ever REMOVE a trade, never add one and never move one.
        const bool allowBuy  = (dirs[di] == XPDIR_BUY);
        const bool allowSell = (dirs[di] == XPDIR_SELL);
        CHECK(got_buy  == (ref_buy  && allowBuy),
              "VETO buy side wrong", m, active, isBuy, buyX, sellX, di);
        CHECK(got_sell == (ref_sell && allowSell),
              "VETO sell side wrong", m, active, isBuy, buyX, sellX, di);
        // the defining property: a veto is a subset of 1.03, never a superset
        CHECK(!(got_buy && !ref_buy) && !(got_sell && !ref_sell),
              "VETO created a trade 1.03 would not have taken",
              m, active, isBuy, buyX, sellX, di);
        if ((ref_buy && !got_buy) || (ref_sell && !got_sell)) vetoBlocked++;
        if ((ref_buy && got_buy) || (ref_sell && got_sell)) vetoAllowed++;
      } else {
        // DIR_TRANSLATE: with no candidate, either crossing fires the side the
        // ladder picked - and nothing fires when the ladder says NONE.
        if (!g_EntryHoldCandidate.active) {
          const bool anyX = (buyX != 0) || (sellX != 0);
          CHECK(got_buy  == (anyX && dirs[di] == XPDIR_BUY),
                "TRANSLATE buy side wrong", m, active, isBuy, buyX, sellX, di);
          CHECK(got_sell == (anyX && dirs[di] == XPDIR_SELL),
                "TRANSLATE sell side wrong", m, active, isBuy, buyX, sellX, di);
          if (anyX && dirs[di] == XPDIR_NONE)
            CHECK(!got_buy && !got_sell, "TRANSLATE fired with dir=NONE",
                  m, active, isBuy, buyX, sellX, di);
          // a sell crossing executing a buy is the fade the report names
          if (sellX && !buyX && dirs[di] == XPDIR_BUY && got_buy) translateFlipped++;
        } else {
          CHECK(got_buy == buyHoldActive && got_sell == sellHoldActive,
                "TRANSLATE broke the live hold candidate", m, active, isBuy, buyX, sellX, di);
        }
        g_VirtualBuyStopPrice = 111.0; g_VirtualSellStopPrice = 222.0;
        XPDir_ClearTriggerLevels();
        CHECK(g_VirtualBuyStopPrice == 0.0 && g_VirtualSellStopPrice == 0.0,
              "TRANSLATE did not zero both trigger levels", m, active, isBuy, buyX, sellX, di);
        translateActed++;
      }
    }
  }

  printf("gate0 entry-path: states=%d checks=%d failures=%d\n", 4 * 2 * 2 * 2 * 2 * 3, checks, failures);
  printf("  DIR_OFF divergences from 1.03: %d (must be 0)\n", offDiffers);
  printf("  DIR_LOCK states exercised: %d   DIR_TRANSLATE states exercised: %d\n",
         lockActed, translateActed);
  printf("  DIR_TRANSLATE fades observed (sell crossing -> buy executes): %d (must be > 0)\n",
         translateFlipped);
  printf("  DIR_VETO states: %d blocked a 1.03 trade, %d allowed one (never added one)\n",
         vetoBlocked, vetoAllowed);
  if (translateFlipped == 0) { printf("  FAIL no fade path exercised\n"); failures++; }
  if (vetoBlocked == 0) { printf("  FAIL veto never blocked anything\n"); failures++; }
  return failures == 0 ? 0 : 1;
}
