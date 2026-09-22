//+------------------------------------------------------------------+
//| SpeedAlert_DirectionRouter_Test_EA.mq5                           |
//| Standalone theory-test EA for XAUUSD M1.                          |
//| MaxTrailingMultiplier is the speed alert only; direction comes     |
//| from candle/body, order-flow, spread, micro-break, and validation. |
//+------------------------------------------------------------------+
#property strict
#property version   "1.500-XPDIR"
#property description "SpeedAlert candle-gated test candidate: current M1 prefix required for market signals; existing continuation freeze and speed trailing retained. | XPW direction veto (InpDirMode=DIR_OFF reproduces the unfiltered EA)."

#include <Trade/Trade.mqh>
#include "SpeedAlertContinuationFilter.mqh"
#include "TheoryMT5HistoryEntryQualityShadowV1.mqh"
#include "TheoryJourneyQualityShadowV2.mqh"
#include "XPW_DirectionLadder.mqh"   // XPDIR: the direction ladder

//+------------------------------------------------------------------+
//| XPDIR: the direction veto.                                        |
//|                                                                    |
//| This EA keeps its own trigger AND its own direction. The ladder    |
//| only refuses an ENTRY whose side it disagrees with, and only when  |
//| InpDirMode = DIR_VETO. In DIR_OFF (the default) XPDir_AllowsRequest|
//| returns true for everything and this class is a pass-through.      |
//|                                                                    |
//| Subclassed here rather than edited into SpeedAlertContinuationFilter|
//| .mqh so that every .mqh in the package stays byte-identical.        |
//|                                                                    |
//| Closes are never blocked: XPDir_IsEntryRequest passes anything with|
//| request.position or position_by set, every SLTP/MODIFY/REMOVE, and |
//| on a netting account any order that reduces an open position.      |
//+------------------------------------------------------------------+
class CXPDirContinuationTrade : public CContinuationTrade
{
public:
   virtual bool OrderSend(const MqlTradeRequest &request, MqlTradeResult &result)
   {
      if(XPDir_AllowsRequest(request))
         return CContinuationTrade::OrderSend(request, result);
      ZeroMemory(result);
      result.retcode = TRADE_RETCODE_REJECT;
      result.comment = "XPDIR_VETO";
      return false;
   }
};

CXPDirContinuationTrade trade;

const double ROUTER_BIG_VALUE = 1000000000.0;

enum RouterMode
{
   StopOnly = 0,
   StopAndMarket = 1,
   StopMarketLimit = 2
};

enum RouterAction
{
   ActSkip = 0,
   ActBuyStop = 1,
   ActSellStop = 2,
   ActBuyMarket = 3,
   ActSellMarket = 4,
   ActBuyLimit = 5,
   ActSellLimit = 6
};

enum SpeedThresholdMode
{
   FIXED = 0,
   PERCENTILE = 1
};

struct MasterVwapTelemetry
{
   bool   valid;
   bool   degraded;
   bool   heartbeatAvailable;
   long   ageMs;
   double value;
   int    contributors;
   double brokerMid;
};

#include "CaptureLatch.mqh"

struct DirectionState
{
   SARCaptureLatch capture;
   MasterVwapTelemetry capturedMasterVwap;
   double buyScore;
   double sellScore;
   bool spreadStable;
   int bodyDir;
   int microDir;
   int flowDir;
   bool flowFresh;
   bool flowAgreesWithWinner;
   bool flowDisagreesWithWinner;
   bool follow21;
   bool follow37;
   bool oppositePressure;
   bool snapback;
   bool continuation;
   bool exhaustion;
   bool retestHeld;
   bool retestFailed;
   double bodyPts;
   double upperWickPts;
   double lowerWickPts;
   double forceImb;
   double nearImb;
   double bookImb;
   double mfe;
   double mae;
   string scenario;
   string labels;
};

struct TheoryAIPreEntryJourneyContextV1
{
   bool   valid;
   long   decision_ms;
   string session_bucket;
   double spread_points;
   double velocity_1s_with_trade;
   double velocity_3s_with_trade;
   double velocity_5s_with_trade;
   double velocity_1s_minus_3s_with_trade;
   double velocity_3s_minus_5s_with_trade;
   double force_imbalance_with_trade;
   double near_imbalance_with_trade;
   double book_imbalance_with_trade;
   int    body_direction_with_trade;
   int    micro_direction_with_trade;
   int    flow_direction_with_trade;
   bool   flow_fresh;
   bool   opposite_pressure;
   bool   continuation;
   bool   exhaustion;
   bool   retest_held;
   bool   retest_failed;
   double own_direction_score;
   double opposite_direction_score;
   double direction_score_edge;
};

struct TheoryAIT200ShadowV2Path
{
   ulong  position_ticket;
   ulong  position_identifier;
   string decision_identity;
   string route;
   long   decision_time_msc;
   long   fill_time_msc;
   int    side;
   double entry_price;
   double initial_sl;
   double active_stop;
   double mfe_points;
   double mae_points;
   bool   initial_sl_valid;
   bool   start_logged;
   bool   terminal_pending;
   string pending_event;
   long   pending_event_time_msc;
   double pending_gross_points;
   bool   pending_sample_valid;
   string pending_causal_status;
   bool   armed;
   long   arm_time_msc;
   string arm_rhythm;
   string current_rhythm;
};

input string     Inp01_General              = "=== General ===";
input bool       TradingEnabled             = true;
input long       MagicNumber                = 26090568;
input double     FixedLot                   = 0.05;
input int        SlippagePoints             = 50;
input RouterMode EntryRouterMode            = StopMarketLimit;
input int        MaxOpenPositions           = 1;
input int        MaxPendingOrders           = 1;
input bool       ScenarioIndependentPerformance = true;
input int        MaxOpenPositionsPerScenario = 1;
input int        MaxPendingOrdersPerScenario = 1;
input bool       CancelOnlySameScenarioPendings = true;
input bool       CancelOldPendings          = true;
input int        PendingExpirySeconds       = 25;
input int        ScenarioCapLogCooldownSeconds = 10;
input string     CsvLogFileV483Cost         = "SpeedAlert_Continuation_v1497_RETEST_scenario.csv";
input bool       InpUseSplitStopFloor       = false;
input bool       InpUseTrueStopRiskSizing   = false;
input double     InpCalibrationRiskPercent  = 1.0;
input bool       InpUseSlippageInstrumentation = true;
input bool       InpUseExitReasonAudit      = true;
input string     InpExecutionAuditLogFile   = "SpeedAlert_Continuation_v1497_RETEST_execution.csv";
input bool       UseDefensiveCloseLockout   = true;
input int        DefensiveLockoutCloseCount = 3;
input int        DefensiveLockoutSeconds    = 90;
input int        DefensiveLockoutLogCooldownSeconds = 10;
input bool       DefensiveLockoutCancelPendings = true;
input int        CloseDuplicateMemoryMs     = 10000;
input string     Inp01A_AIShadow            = "=== Research-only AI Shadow ===";
input string     InpAIShadowLogFile         = "SpeedAlert_Continuation_v1497_RETEST_ai_shadow.csv";
input bool       InpAIJourneyShadowEnabled  = true;
input string     InpAIJourneyShadowLogFile  = "SpeedAlert_Continuation_v1497_RETEST_ai_journey.csv";
input bool       InpAIHardGateEnabled       = false;
input bool       InpAIRiskAdjustEnabled     = false;

input string     Inp02_SpeedAlert           = "=== MaxTrailingMultiplier Speed Alert ===";
input double     MaxTrailingMultiplier      = 7.5;
input int        SpeedLookbackSeconds       = 10;
input double     MinSpeedAlertPoints        = 37.0;
input int        SpeedAlertHoldSeconds      = 20;
input SpeedThresholdMode InpSpeedThresholdMode = FIXED;
input double     InpSpeedPercentile         = 99.0;
input int        InpSpeedWindowSamples      = 2000;
input bool       InpUseHighBurstGate        = false;
input SpeedThresholdMode InpBurstThresholdMode = FIXED;
input double     InpBurstThresholdPts       = 172.0;
input double     InpBurstPercentile         = 99.0;
input int        InpBurstWindowSamples      = 2000;
input double     SpeedDirectionScore        = 1.0;
input bool       UsePreSpeedRadar           = true;
input double     PreSpeedEarlyRatio         = 0.5;
input double     PreSpeedStrongRatio        = 0.7;
input int        PreSpeedLogCooldownSeconds = 10;
input bool       UsePreSpeedAgainstDefense  = true;
input double     PreSpeedAgainstDefenseMinLossPoints = 21.0;
input bool       PreSpeedAgainstDefenseHardClose = true;
input double     PreSpeedAgainstDefenseHardMaxLossPoints = 25.0;
input bool       EXHLPreSpeedDangerClose    = true;
input double     EXHLPreSpeedDangerLossPoints = 37.0;
input bool       EXHLPreSpeedDangerNeedsOppositePressure = true;
input bool       FOLMMarketDangerClose      = true;
input double     FOLMMarketDangerLossPoints = 37.0;
input bool       FOLMMarketDangerNeedsOppositePressure = true;
input double     FOLMFlowDisagreeDangerLossPoints = 37.0;
input bool       FOLMMarketHardClose         = true;
input double     FOLMMarketHardMaxLossPoints = 25.0;
input string     FOLMMarketHardCloseComment = "SA_FOLM_MARKET_HARD";
input bool       FOLMSellMarketEarlyDangerClose = true;
input double     FOLMSellMarketEarlyDangerLossPoints = 18.0;
input bool       FOLMSellMarketEarlyDangerNeedsOppositePressure = false;
input string     FOLMSellMarketEarlyDangerCloseComment = "SA_FOLM_SM_EARLY";
input int        PreSpeedAgainstDefenseNoFollowSeconds = 6;
input bool       PreSpeedAgainstDefenseNeedsOppositePressure = true;
input bool       PreSpeedAgainstDefenseCloseOnPreSpeed50 = true;
input bool       PreSpeedAgainstDefenseCloseOnPreSpeed70 = true;
input bool       FlowDisagreeMakesDefenseImmediate = true;
input bool       FLXQSellStopFastPreSpeedDefense = true;
input int        FLXQSellStopPreSpeedDefenseNoFollowSeconds = 4;
input double     FLXQSellStopFastPreSpeedDefenseLossPoints = 18.0;
input bool       FLXQSellStopFastPreSpeedDefenseNeedsOppositePressure = false;
input bool       FLXQSellStopPressureDangerClose = true;
input double     FLXQSellStopPressureDangerLossPoints = 25.0;
input string     FLXQSellStopPressureDangerCloseComment = "SA_FLXQ_SS_PRESSURE";
input bool       UseStopFlowDisagreeDangerClose = true;
input double     StopFlowDisagreeDangerLossPoints = 37.0;
input int        StopFlowDisagreeDangerMinHoldMs = 0;
input bool       StopFlowDisagreeDangerNeedsOppositePressure = true;
input string     StopFlowDisagreeDangerCloseComment = "SA_STOP_FLOW_DANGER";
input int        PreSpeedAgainstDefenseMaxSignalAgeMs = 8000;
input string     PreSpeedAgainstDefenseCloseComment = "SA_PRE_SPEED_DEFENSE";
input int        PreSpeedAgainstDefenseRetryLogCooldownMs = 1000;

input string     Inp03_DirectionScore       = "=== Pre Entry Direction Score ===";
input double     MinDirectionScore          = 5.0;
input double     MinScoreEdge               = 3.0;
input int        CandleIndexToCheck         = 0;
input double     MinCandleBodyPoints        = 21.0;
input double     CandleBodyScore            = 2;
input int        MicroBreakLookbackSeconds  = 10;
input double     MicroBreakBufferPoints     = 5;
input double     MicroBreakScore            = 3;
input double     MaxSpreadPoints            = 45;
input double     SpreadStableScore          = 2.0;

input string     Inp04_OrderFlow            = "=== Order Flow Global Variables ===";
input bool       UseOrderFlow               = true;
input string     FlowGVPrefix               = "XPW_XAU_";
input int        MaxFlowAgeMs               = 4000;
input double     MinFlowImbalance           = 5.0;
input double     FlowComponentScore         = 1.0;
input bool       BlockStrongFlowAgainst     = false;
input bool       DowngradeNeutralSellMarketToStop = true;
input bool       WeakFlowMarketNeedsBodyAndMicro = true;
input double     WeakFlowMarketMinScore     = 5.0;
input double     WeakFlowMarketMinScoreEdge = 2.0;

input string     Inp05_EntryRouting         = "=== Entry Routing ===";
input double     StopEntryDistancePoints    = 35.0;
input double     LimitRetestDistancePoints  = 35.0;
input double     MarketFollow21Points       = 21.0;
input int        MarketFollow21Seconds      = 10;
input double     MarketFollow37Points       = 37.0;
input int        MarketFollow37Seconds      = 30;
input double     StopSLPoints               = 90.0;
input double     StopTPPoints               = 180.0;
input double     MarketSLPoints             = 80.0;
input double     MarketTPPoints             = 160.0;
input double     LimitSLPoints              = 90.0;
input double     LimitTPPoints              = 160.0;
input double     BodyOnlyLotFactor          = 0.65;
input double     ContinuationStopLotFactor  = 1.0;
input double     FollowThroughMarketLotFactor = 1.0;
input double     ExhaustionLimitLotFactor   = 0.5;
input bool       InpUseEntryHold            = true;
input int        InpEntryHoldMs             = 1100;
input double     InpEntryHoldMinFavPoints   = 5.0;
input bool       InpUsePrior60Filter        = true;
input bool       InpUse1000msHold           = true;
input double     InpHoldMinFavPts           = 5.0;

input string     Inp06_PostValidation       = "=== Post Entry Validation ===";
input bool       UsePostEntryValidation     = true;
input double     OppositePressurePoints     = 21.5;
input int        OppositePressureSeconds    = 5;
input bool       CloseIfNoFollowThrough     = true;
input int        ValidationSeconds          = 30;
input bool       CloseOnRetestFailure       = true;
input double     RetestFailPoints           = 10.0;
input double     RetestFailCloseMinLossPoints = 37.0;
input bool       RetestFailedEarlyClose     = true;
input double     RetestFailedEarlyLossPoints = 25.0;
input bool       RetestFailedEarlyBypassHold = true;
input string     RetestFailedEarlyCloseComment = "SA_RETEST_EARLY";
input bool       FOLMAfterFollowRetestDangerClose = true;
input double     FOLMAfterFollowRetestDangerLossPoints = 37.0;
input bool       FOLMAfterFollowRetestBypassHold = true;
input string     FOLMAfterFollowRetestDangerCloseComment = "SA_FOLM_RETEST_DANGER";
input int        RetestFailConfirmSeconds   = 2;
input string     RetestFailedCloseComment   = "SA_RETEST_FAILED";
input bool       UseEmergencyRetestCollapseClose = true;
input double     RetestCollapseMinLossPoints = 37.0;
input double     RetestCollapseVelocityPointsPerSec = 35.0;
input double     RetestCollapseJumpPoints   = 21.0;
input int        RetestCollapseLookbackMs   = 1000;
input int        RetestCollapseConfirmTicks = 2;
input int        RetestCollapseConfirmMs    = 250;
input int        RetestCollapseHoldNormalCloseMs = 1000;
input double     RetestCollapseHardMaxLossPoints = 75.0;
input string     RetestCollapseHardCloseComment = "SA_RETEST_HARD_FLOOR";
input int        RetestHardFloorRetryLogCooldownMs = 1000;
input int        RetestCollapseRetryLogCooldownMs = 1000;
input int        RetestPauseLogCooldownMs = 1000;
input string     RetestCollapseCloseComment = "SA_RETEST_COLLAPSE";
input bool       NoFollowEarlyClose         = true;
input int        NoFollowEarlySeconds       = 12;
input double     NoFollowEarlyLossPoints    = 25.0;
input bool       NoFollowEarlyNeedsOppositePressure = true;
input string     NoFollowEarlyCloseComment  = "SA_NO_FOLLOW_EARLY";
input double     NoFollowCloseMinLossPoints = 37.0;
input string     NoFollowCloseComment       = "SA_NO_FOLLOW";
input bool       UseSpeedProfitExit         = true;
input double     SpeedProfitExitPoints      = 100.0;
input bool       RequireProfitSideSpeed     = true;
input string     SpeedProfitExitComment     = "SA_PROFIT_EXIT";
input int        SpeedProfitExitRetrySeconds = 2;
input int        SpeedProfitExitMaxRetries  = 8;
input bool       UsePredictiveSpeedProfitExit = true;
input double     PredictiveExitMinProfitPoints = 250;
input double     PredictiveExitMinProjectedNetPoints = 37.0;
input int        PredictiveExitLatencyMs    = 250;
input int        PredictiveExitVelocityLookbackMs = 1000;
input double     PredictiveExitVelocityMultiplier = 1.5;
input double     PredictiveExitExtraBufferPoints = 5.0;
input double     PredictiveExitMinRiskBufferPoints = 21.0;
input double     PredictiveExitMaxRiskBufferPoints = 180.0;
input bool       BlockSpeedExitIfProjectedNegative = true;

input string     Inp07_Trailing             = "=== Simple Test Trailing ===";
input bool       UseTrailing                = true;
input double     TrailStartPoints           = 130;
input double     TrailBehindPoints          = 60;
input double     TrailStepPoints            = 21;

input bool       InpWaitForBurstSettle        = true;
input int        InpBurstSettleQuietMs        = 3000;
input double     InpBurstSettleSpeedFraction  = 0.35;
input double     InpBurstSettleMaxSpeedPipsSec = 300;
input double     InpBurstSettlePullbackPips    = 300;

input string     Inp07A_TrailLayer          = "=== Spread-Scaled Broker Trail Layer ===";
input bool       InpUseTrailLayer           = false;
input double     internalOrderDistance      = 3.0;
input double     internalMinTrailing        = 3.33333333;
input double     internalMaxTrailing        = 6.6666667;
input double     internalMultiplier         = 2.0;
input double     InpReferenceSpreadPts      = 30.0;
input double     InpTrailOuterCapPts        = 200.0;
input double     InpStopBufferPts           = 3.0;
input int        InpModifyMinIntervalMs     = 1000;
input bool       InpArmOnFavPts             = true;
input double     InpTrailArmFavPts          = 35.0;
input bool       InpArmOnCostDigested       = true;
input bool       InpArmOnTimeMs             = false;
input int        InpTrailArmTimeMs          = 2900;
input double     InpCommissionPts           = 0.0;
input double     InpExitSlipReservePts      = 14.0;
input double     InpCostLockInPts           = 0.0;

input string     Inp08_Visuals              = "=== Speed Alert Chart Visuals ===";
input bool       ShowSpeedVisuals           = true;
input bool       SpeedVisualDrawImpulseLine = false;
input bool       SpeedVisualDrawNextDistance = true;
input bool       SpeedVisualShowAlertText   = false;
input bool       SpeedVisualShowDistanceText = false;
input int        SpeedVisualKeepAlerts      = 30;
input int        SpeedVisualMarkerCode      = 159;
input double     SpeedVisualTextOffsetPoints = 15.0;
input color      SpeedVisualBuyColor        = clrDeepSkyBlue;
input color      SpeedVisualSellColor       = clrTomato;
input color      SpeedVisualDistanceColor   = clrGold;
input string     SpeedVisualPrefix          = "SAR_SPEED_";
input bool       SpeedVisualCleanOldOnInit  = true;
input bool       SpeedVisualDeleteOnDeinit  = false;

input string     Inp09_SlippageLog         = "=== Passive Slippage Measurement ===";
input bool       LogSlippageMeasurement     = true;
input string     Inp10_PassiveTelemetry     = "=== v35 Passive Warning Telemetry ===";
input bool       UsePassiveWarningTelemetry = true;
input bool       LogFOLMPreHardWarnings     = true;
input bool       LogRetestPreFailWarnings   = true;
input double     PassiveWarnLevel1Points    = 15.0;
input double     PassiveWarnLevel2Points    = 18.0;
input double     PassiveWarnLevel3Points    = 21.0;
input double     PassiveWarnLevel4Points    = 24.0;
input string     Inp11_V36FOLMActiveClose   = "=== v36 FOLM Warning Active Close ===";
input bool       UseFOLMPreHardWarnActiveClose = true;
input double     FOLMPreHardWarnActiveClosePoints = 24.0;
input string     FOLMPreHardWarnActiveCloseComment = "SA_FOLM_WARN24";
input string     Inp12_V40ExecutionShield   = "=== v40 Emergency Execution Shield ===";
input bool       UseV40ExecutionShield      = true;
input bool       V40PreSpeedExecutionShield = true;
input double     V40PreSpeedExecutionShieldLossPoints = 18.0;
input bool       V40PreSpeedExecutionShieldNeedsPressureOrFlow = true;
input string     V40PreSpeedExecutionShieldCloseComment = "SA_V40_PRE_SPEED_SHIELD";
input bool       V40FLXQSellStopPressureShield = true;
input double     V40FLXQSellStopPressureShieldLossPoints = 18.0;
input bool       V40FLXQSellStopPressureShieldNeedsPressure = true;
input string     V40FLXQSellStopPressureShieldCloseComment = "SA_V40_FLXQ_SS_SHIELD";
input bool       V40RetestExecutionShield   = true;
input double     V40RetestExecutionShieldLossPoints = 21.0;
input int        V40RetestExecutionShieldMinWarningAgeMs = 250;
input double     V40RetestExecutionShieldMinVelocityPointsPerSec = 25.0;
input double     V40RetestExecutionShieldMinJumpPoints = 10.0;
input bool       V40RetestExecutionShieldNeedsPressure = true;
input string     V40RetestExecutionShieldCloseComment = "SA_V40_RETEST_SHIELD";
input string     Inp13_V41TelemetryOnly     = "=== v41 FOLM Tick-Gap Telemetry Only ===";
input bool       UseV41FOLMTickGapTelemetry = true;
input string     Inp14_V42JumpDirectionTelemetry = "=== v42 Tick-Jump Direction Telemetry Only ===";
input bool       UseV42JumpDirectionTelemetry = true;
input string     Inp15_V43EarlyJumpTelemetry = "=== v43 Entry/Early Jump Telemetry Only ===";
input bool       UseV43EarlyJumpTelemetry = true;
input string     Inp16_V44ShadowReplayTelemetry = "=== v44 Shadow Replay / FOLM:SM Ghost Only ===";
input bool       UseV44ShadowReplayTelemetry = true;
input double     V44ShadowFirst1sAdverseJumpPoints = 15.0;
input double     V44ShadowFirst2sAdverseJumpPoints = 18.0;
input bool       UseV44FOLMSGhostTracker = true;
input double     V44FOLMSGhostWinPoints = 100.0;
input double     V44FOLMSGhostLossPoints = 24.0;
input int        V44FOLMSGhostMaxSeconds = 30;
input string     Inp17_V45FOLMQualityTelemetry = "=== v45 FOLM Quality Telemetry Only ===";
input bool       UseV45FOLMQualityTelemetry = true;
input double     V45FOLMLowQualityScore = 45.0;
input double     V45FOLMHighQualityScore = 70.0;
input double     V45FOLMFav2sTargetPoints = 20.0;
input double     V45FOLMFav3sTargetPoints = 24.0;
input double     V45FOLMFirst10sMfeTargetPoints = 75.0;
input bool       UseV45PreEntryHighShadowTelemetry = true;
input double     V45PreEntryHighShadowScore = 70.0;
input double     V45PreEntryMidShadowScore = 45.0;
input string     Inp18_V451ProofTelemetry = "=== v45.1 Candidate Proof Telemetry Only ===";
input bool       UseV451ProofTelemetry = true;
input double     V451LOWJFirst1sAdversePoints = 10.0;
input double     V451LOWJFirst2sAdversePoints = 12.0;
input string     Inp19_V452LowWinnerMicroscope = "=== v45.2 LOW Winner Microscope Telemetry Only ===";
input bool       UseV452LowWinnerMicroscope = true;
input double     V452LowDeadMfeCeilingPoints = 20.0;
input double     V452LowEscapeMfeFloorPoints = 50.0;
input string     Inp20_V46LowDeadShadowReplay = "=== v46 LOW Dead Shadow Replay Only ===";
input bool       UseV46LowDeadShadowReplay = true;
input int        V46LowDeadShadowMinAgeMs = 3000;
input double     V46LowDeadShadowMaxFav1To3Points = 0.0;
input double     V46LowDeadShadowMfeCeilingPoints = 20.0;
input bool       V46LowDeadShadowRequireCurrentFavNonPositive = true;
input string     Inp21_V461MicroTelemetry = "=== v46.1 LOW/HIGH-MID Microscope Telemetry Only ===";
input bool       UseV461MicroTelemetry = true;
input double     V461Mfe10LevelPoints = 10.0;
input double     V461Mfe20LevelPoints = 20.0;
input double     V461Mfe40LevelPoints = 40.0;
input double     V461OppositeSpeedPoints = 100.0;
input double     V461OppositeHardLossPoints = 24.0;

input string     Inp22_V47DecisionFrontierTelemetry = "=== v47 Decision-Time Frontier Telemetry Only ===";
input bool       UseV47DecisionFrontierTelemetry = true;
input double     V47LowNoTradeFavCeilingPoints = 0.0;
input double     V47LowNoTradeMaxFav1To3Points = 0.0;
input double     V47EarlyAdverseJumpPoints = 12.0;
input int        V47DecisionFrontierMaxMs = 3000;
input string     Inp23_V471TelemetryRepair = "=== v47.1 Telemetry Repair / Tick Frontier Only ===";
input bool       UseV471TelemetryRepair = true;
input int        V471TickCapsuleCount = 8;
input double     V471EarlyFavCeilingPoints = 0.0;
input double     V471AdverseJumpPoints = 12.0;
input int        V471TapeDeadMaxTicks500ms = 2;
input int        V471TapeDeadMaxTicks1000ms = 4;
input string     Inp24_V48Mode2ShadowScorecard = "=== v48.2 Mode 2 BODY+Align Shadow Scorecard Only ===";
input bool       UseV48Mode2ShadowScorecard = true;
input bool       V48Mode2BodyNeedsVelocityAlign = true;
input int        V48Mode2VelocityAlignLookbackMs = 1000;
input int        V48Mode2MaxOppositeFlags = 2;
input double     V48Mode2MaxSpreadPoints = 15.0;
input string     V48Mode2BlockedHoursCSV = "12,22,23";
input double     V48Mode2BodyLotFactorForScorecard = 0.65;

#include "ContinuationInputs.mqh"
#include "SpeedTrailInputs.mqh"
#include "EffectiveInputs.generated.mqh"

long   tickMs[];
double tickMid[];
double tickSpread[];
double speedOneSecondObservations[];
long   burstEpochStartMs = 0;

const double SERVER_STOP_BUFFER_POINTS = 3.0;
const string SAR_TRAIL_LAYER_FILE = "SAR_TrailLayer_v1.csv";
const string SAR_GATE_STACK_FILE = "SAR_GateStack_v1.csv";
const string SAR_ORDER_FLOW_DECISION_V2_FILE = "SAR_OrderFlowDecision_v2.csv";
const string SAR_TRAIL_GEOMETRY_ERROR = "SAR_TRAIL_GEOMETRY_PAIR_MISMATCH";

double sarTickSize = 0.0;
double sarTickValue = 0.0;
double sarMinLegalPts = 0.0;
double sarCostDigestedPts = 0.0;

bool           entryHoldArmed = false;
long           entryHoldSignalMs = 0;
double         entryHoldSignalMid = 0.0;
datetime       entryHoldSignalBar = 0;
datetime       entryHoldFailedBar = 0;
RouterAction   entryHoldAction = ActSkip;
DirectionState entryHoldDirectionState;

double lastSpeedComputedThreshold = 0.0;
double lastSpeedGateValue = 0.0;
int    lastSpeedThresholdSamples = 0;
bool   lastBurstAvailable = false;
double lastBurstSignedPoints = 0.0;
double lastBurstAbsPoints = 0.0;
double lastBurstResolvedThreshold = 0.0;
bool   lastBurstThresholdAvailable = false;
int    lastBurstThresholdSamples = 0;

struct GateDecisionSnapshot
{
   long decisionId;
   long timeMsc;
   RouterAction action;
   int side;
   bool burstAvailable;
   double burstSignedPoints;
   double burstAbsPoints;
   bool burstThresholdAvailable;
   double burstThresholdPoints;
   int burstThresholdSamples;
   bool burstPass;
   bool friendlyAvailable;
   double friendly60DriftPoints;
   bool friendlyPass;
};

long gateDecisionSequence = 0;
bool gateFileErrorLogged = false;
bool trailFileErrorLogged = false;
bool orderFlowDecisionFileErrorLogged = false;

struct ExitProfitGateState
{
   long positionId;
   int side;
   bool released;
};
ExitProfitGateState exitProfitGateStates[];
const uint SAR_RETCODE_EXIT_PROFIT_GATE = 50068;

struct BurstSettleState
{
   long positionId;
   int side;
   double entry;
   long firstMs;
   long lastMs;
   double lastBid;
   double lastAsk;
   double bestMid;
   double bestBid;
   double bestAsk;
   double peakSpeed;
   long quietSinceMs;
   bool allowed;
};
BurstSettleState burstSettleStates[];


struct TrailLayerPositionState
{
   ulong ticket;
   ulong positionId;
   long fillTimeMsc;
   int side;
   double entryPrice;
   double peakExecutable;
   bool trailArmed;
   string armTrigger;
   long armTimeMsc;
   long lastTrailEvaluationMsc;
   bool holdEvaluated;
};

TrailLayerPositionState trailLayerStates[];

struct StopFloorLogState
{
   ulong  ticket;
   double calculatedPoints;
   double floorPoints;
   double appliedPoints;
   string winningTerm;
};
StopFloorLogState stopFloorLogStates[];

bool   speedActive = false;
long   speedStartMs = 0;
double speedStartMid = 0.0;
int    speedDir = 0;
double speedPoints = 0.0;
long   preSpeedEarlyLastLogMs = 0;
int    preSpeedEarlyLastDir = 0;
long   preSpeedStrongLastLogMs = 0;
int    preSpeedStrongLastDir = 0;
long   preSpeedLastSignalMs = 0;
int    preSpeedLastSignalDir = 0;
int    preSpeedLastSignalLevel = 0;
double preSpeedLastSignalMove = 0.0;
double preSpeedLastSignalRatio = 0.0;
double preSpeedLastSignalV1 = 0.0;
double preSpeedLastSignalV3 = 0.0;
double preSpeedLastSignalV5 = 0.0;

ulong  trackedTickets[];
ulong  positionTrackLoggedTickets[];
ulong  closingTickets[];
long   closingTicketMs[];
string closingTicketEvents[];
ulong  closeLoggedTickets[];
long   closeLoggedTicketMs[];
string closeLoggedTicketEvents[];
long   trackedEntryMs[];
double trackedEntries[];
int    trackedSides[];
double trackedMfes[];
double trackedMaes[];
bool   trackedHit21s[];
bool   trackedHit37s[];
bool   trackedRetestHelds[];
bool   trackedRetestFaileds[];
double trackedFirst10sMfes[];
int    trackedTickCounts[];
double trackedMaxSingleTickAdversePts[];
double trackedLastTickDeltaPts[];
int    trackedEntryTickJumpWithTrades[];
int    trackedEntryTickJumpAgainstTrades[];
double trackedFirst500msMaxAdverseJumpPts[];
double trackedFirst1sMaxAdverseJumpPts[];
double trackedFirst2sMaxAdverseJumpPts[];
double trackedFirst250msMaxAdverseJumpPts[];
double trackedFirst750msMaxAdverseJumpPts[];
bool   trackedV44First1sShadowFired[];
long   trackedV44First1sShadowMs[];
double trackedV44First1sShadowFav[];
bool   trackedV44First2sShadowFired[];
long   trackedV44First2sShadowMs[];
double trackedV44First2sShadowFav[];
bool   trackedV451LowJFirst1sFired[];
long   trackedV451LowJFirst1sMs[];
double trackedV451LowJFirst1sFav[];
bool   trackedV451LowJFirst2sFired[];
long   trackedV451LowJFirst2sMs[];
double trackedV451LowJFirst2sFav[];
string trackedV451FlowOppSourceTiming[];
long   trackedV451FlowOppSourceMs[];
double trackedV451FlowOppSourceFav[];
bool   trackedV46LowDeadShadowFired[];
long   trackedV46LowDeadShadowMs[];
double trackedV46LowDeadShadowFav[];
double trackedV46LowDeadShadowMfe[];
double trackedV46LowDeadShadowMaxFav1To3[];
string trackedV46LowDeadShadowReason[];
int    trackedPreWarn15JumpAgainstTrades[];
int    trackedPreWarn18JumpAgainstTrades[];
int    trackedPreWarn21JumpAgainstTrades[];
int    trackedPreWarn24JumpAgainstTrades[];
long   trackedLastQuoteGapMs[];
long   trackedLastTelemetryTickMs[];
long   trackedFOLMWarn15Ms[];
long   trackedFOLMWarn18Ms[];
long   trackedFOLMWarn21Ms[];
long   trackedFOLMWarn24Ms[];
int    trackedFOLMWarn24Ticks[];
double trackedFavAt250ms[];
double trackedFavAt500ms[];
double trackedFavAt1s[];
double trackedFavAt2s[];
double trackedFavAt3s[];
double trackedFavAt100ms[];
double trackedFavAt750ms[];
double trackedFavAt1500ms[];
bool   trackedAliveAt100ms[];
bool   trackedAliveAt250ms[];
bool   trackedAliveAt500ms[];
bool   trackedAliveAt750ms[];
bool   trackedAliveAt1s[];
bool   trackedAliveAt1500ms[];
bool   trackedAliveAt2s[];
bool   trackedAliveAt3s[];
long   trackedSampleMsAt100ms[];
long   trackedSampleMsAt250ms[];
long   trackedSampleMsAt500ms[];
long   trackedSampleMsAt750ms[];
long   trackedSampleMsAt1s[];
long   trackedSampleMsAt1500ms[];
long   trackedSampleMsAt2s[];
long   trackedSampleMsAt3s[];
int    trackedTicksAt100ms[];
int    trackedTicksAt250ms[];
int    trackedTicksAt500ms[];
int    trackedTicksAt750ms[];
int    trackedTicksAt1s[];
int    trackedTicksAt1500ms[];
int    trackedTicksAt2s[];
int    trackedTicksAt3s[];
long   trackedTimeToFirstProfitMs[];
long   trackedTimeToMfe10Ms[];
long   trackedTimeToMfe20Ms[];
long   trackedTimeToMfe40Ms[];
long   trackedTimeToSpeedMs[];
bool   trackedFirstProfitSeen[];
double trackedPeakAfterFirstProfit[];
double trackedMaxPullbackAfterFirstProfit[];
double trackedV461LowDetectSpread[];
string trackedV461LowDetectOrderflowState[];
string trackedV461LowDetectPressureState[];
double trackedV461OppAtLowMfe[];
double trackedV461OppAtLowMae[];
bool   trackedV461OppAtLowWouldSpeed[];
bool   trackedV461OppAtLowWouldHardLose[];
double trackedPreEntryHighShadowScores[];
string trackedPreEntryHighShadowBuckets[];
string trackedPreEntryHighWouldAllows[];
string trackedPreEntryHighWouldBlocks[];
string trackedPreEntryHighSignals[];
string trackedV471TickPath[];
string trackedV471PreEntryTapeHealth[];
double trackedV471PreEntryVelocityDecay[];
long   trackedV471PreSpeedSignalAgeMs[];
string trackedV48Mode2Signal[];
string trackedV48Mode2BlockReason[];
int    trackedV48Mode2OppFlags[];
double trackedV48Mode2Velocity1s[];
double trackedV48Mode2WeightFactor[];
long   trackedUrgentCloseStartMs[];
int    trackedFOLMPreHardWarningMasks[];
int    trackedRetestPreFailWarningMasks[];
long   trackedRetestFailStartMs[];
double trackedRetestFailStartFavs[];
long   trackedRetestCollapseStartMs[];
int    trackedRetestCollapseTicks[];
double trackedLastFavs[];
long   trackedLastFavMs[];
string trackedLabels[];
bool   trackedSpeedExitPendings[];
long   trackedSpeedExitLastTryMs[];
int    trackedSpeedExitRetryCounts[];
bool   trackedSpeedExitLimitLogged[];
bool   trackedSpeedExitUnsafeLogged[];
bool   trackedHardFloorUrgentClose[];
long   trackedHardFloorLastLogMs[];
int    trackedHardFloorAttempts[];
bool   trackedRetestCollapseUrgentClose[];
long   trackedRetestCollapseLastLogMs[];
int    trackedRetestCollapseAttempts[];
bool   trackedPreSpeedDefenseUrgentClose[];
long   trackedPreSpeedDefenseLastLogMs[];
int    trackedPreSpeedDefenseAttempts[];
long   trackedRetestPauseLastLogMs[];

ulong  v44GhostTickets[];
long   v44GhostStartMs[];
double v44GhostEntries[];
int    v44GhostSides[];
double v44GhostActualCloseFavs[];
double v44GhostMfes[];
double v44GhostMaes[];
string v44GhostLabels[];
string v44GhostSourceEvents[];

ulong  pendingRequestTickets[];
double pendingRequestPrices[];
int    pendingRequestActions[];
long   pendingRequestDecisionMs[];
TheoryAIPreEntryJourneyContextV1 pendingRequestAIJourneyContexts[];
double pendingRequestPreEntryHighScores[];
string pendingRequestPreEntryHighBuckets[];
string pendingRequestPreEntryHighAllows[];
string pendingRequestPreEntryHighBlocks[];
string pendingRequestPreEntryHighSignals[];
string pendingRequestV471TapeHealth[];
double pendingRequestV471VelocityDecay[];
long   pendingRequestV471PreSpeedSignalAgeMs[];
string pendingRequestV48Mode2Signal[];
string pendingRequestV48Mode2BlockReason[];
int    pendingRequestV48Mode2OppFlags[];
double pendingRequestV48Mode2Velocity1s[];
double pendingRequestV48Mode2WeightFactor[];

TheoryAIT200ShadowV2Path aiT200ShadowPaths[];

const string THEORY_AI_PREENTRY_JOURNEY_V1_FILE =
   "SpeedAlertRouter_XAUUSD_ai_preentry_journey_v1.csv";
const string THEORY_AI_PREENTRY_JOURNEY_V1_SCHEMA =
   "theory.ai.preentry.journey.features.v1";
const string THEORY_AI_PREENTRY_JOURNEY_V1_CONTRACT_HASH =
   "a59d756f78814af98666fbfe6d26e10a5bd8a06478ba197c1be677134af7304e";
const string THEORY_AI_DECISION_ATTEMPT_V1_FILE =
   "SpeedAlertRouter_XAUUSD_ai_decision_attempt_v1.csv";
const string THEORY_AI_DECISION_ATTEMPT_V1_SCHEMA =
   "theory.ai.preorder.decision.attempt.features.v1";
const string THEORY_AI_DECISION_ATTEMPT_V1_CONTRACT_HASH =
   "5956995d50d5857706db00089145e65180afbfcaa08d7e8cd3dc72cf0faa8ed3";
const string THEORY_AI_T200_SHADOW_V2_FILE =
   "SpeedAlertRouter_XAUUSD_ai_t200_rhythm_shadow_v2.csv";
const string THEORY_AI_T200_SHADOW_V2_SCHEMA =
   "speedalert.theory.t200.rhythm.shadow.telemetry.v2";
const string THEORY_AI_T200_SHADOW_V2_CONTRACT_HASH =
   "b380ad10582b30c72f9040db27022d4863310f49336b6296d93fd67aa1ff1ead";
const double THEORY_AI_T200_SHADOW_TRAIL_START_POINTS = 200.0;
const double THEORY_AI_T200_SHADOW_VELOCITY_THRESHOLD = 50.0;
const long   THEORY_AI_T200_SHADOW_HORIZON_MS = 180000;
const long   THEORY_AI_T200_SHADOW_MAX_HORIZON_LAG_MS = 2000;

bool   logTradeMeasurementActive = false;
bool   logRuleTelemetryActive = false;
bool   logDealLedgerActive = false;
bool   logDealCostsComplete = false;
long   logDealPositionIdentifier = 0;
int    logDealLedgerDeals = 0;
double logDealProfitMoney = 0.0;
double logDealCommissionMoney = 0.0;
double logDealSwapMoney = 0.0;
double logDealFeeMoney = 0.0;
double logDealNetMoney = 0.0;
double logRequestedPrice = 0.0;
double logExecutedPrice = 0.0;
double logSlippagePoints = 0.0;
double logAdverseSlippagePoints = 0.0;
long   logRuleTrueMs = 0;
long   logOrderSendMs = 0;
long   logFillMs = 0;
int    logRuleSide = 0;
double logRuleTruePrice = 0.0;
double logSpreadAtRuleTrue = 0.0;
double logSpreadAtSend = 0.0;
double logSpreadAtFill = 0.0;
double logDecisionDriftPoints = 0.0;
double logTimeInTradeSeconds = 0.0;
double logMfeBeforeClose = 0.0;
double logMaeBeforeClose = 0.0;
double logFirst10sMfe = 0.0;
double logFreezeLevelPoints = 0.0;
double logWarningLevelPoints = 0.0;
double logMaxSingleTickAdversePts = 0.0;
int    logTicksFromFillToWarn24 = 0;
long   logMsFromFillToWarn15 = 0;
long   logMsFromFillToWarn18 = 0;
long   logMsFromFillToWarn21 = 0;
long   logMsFromFillToWarn24 = 0;
double logFavAt1s = ROUTER_BIG_VALUE;
double logFavAt2s = ROUTER_BIG_VALUE;
double logFavAt3s = ROUTER_BIG_VALUE;
long   logQuoteGapMs = 0;
double logLastTickDeltaPts = 0.0;
int    logRetryCount = 0;
long   logMsInFrozenState = 0;
string logSessionBucket = "";
string logSpreadRegime = "";
string logTickJumpDirection = "";
string logTickJumpWithTrade = "";
string logTickJumpAgainstTrade = "";
string logJumpFollowedByProfit1s = "";
string logJumpFollowedByLoss1s = "";
string logSessionJumpQuality = "";
string logOrderFlowAgreedDuringJump = "";
string logEntryTickJumpWithTrade = "";
string logEntryTickJumpAgainstTrade = "";
double logFirst500msMaxAdverseJumpPts = 0.0;
double logFirst1sMaxAdverseJumpPts = 0.0;
double logFirst2sMaxAdverseJumpPts = 0.0;
string logPreWarn15JumpAgainstTrade = "";
string logPreWarn18JumpAgainstTrade = "";
string logPreWarn21JumpAgainstTrade = "";
string logPreWarn24JumpAgainstTrade = "";
string logClosedBeforeSnapshot = "";
string logV44ShadowFirst1sFired = "";
long   logV44ShadowFirst1sMs = 0;
double logV44ShadowFirst1sFav = 0.0;
double logV44ShadowFirst1sReplayDelta = 0.0;
string logV44ShadowFirst2sFired = "";
long   logV44ShadowFirst2sMs = 0;
double logV44ShadowFirst2sFav = 0.0;
double logV44ShadowFirst2sReplayDelta = 0.0;
string logV44FOLMSGhostStarted = "";
string logV451LowJFirst1sFired = "";
long   logV451LowJFirst1sMs = 0;
double logV451LowJFirst1sFav = 0.0;
double logV451LowJFirst1sReplayDelta = 0.0;
long   logV451LowJFirst1sLeadMs = 0;
string logV451LowJFirst1sBeforeCurrentShield = "";
string logV451LowJFirst2sFired = "";
long   logV451LowJFirst2sMs = 0;
double logV451LowJFirst2sFav = 0.0;
double logV451LowJFirst2sReplayDelta = 0.0;
long   logV451LowJFirst2sLeadMs = 0;
string logV451LowJFirst2sBeforeCurrentShield = "";
string logV451ActualCloseEvent = "";
double logV451ActualCloseFav = 0.0;
long   logV451ActualCloseHeldMs = 0;
string logV451FlowOppAuditFlag = "";
string logV451FlowOppSourceTiming = "";
long   logV451FlowOppSourceMs = 0;
double logV451FlowOppSourceFav = 0.0;
string logV45FOLMQualityScore = "";
string logV45FOLMQualityBucket = "";
string logV45FOLMLowQualityWouldBlock = "";
string logV45FOLMLowQualityReplayDelta = "";
string logV45FOLMFav2sBucket = "";
string logV45FOLMFav3sBucket = "";
string logV45FOLMFirst10sMfeBucket = "";
string logV45PreEntryHighShadowScore = "";
string logV45PreEntryHighShadowBucket = "";
string logV45PreEntryHighWouldAllow = "";
string logV45PreEntryHighWouldBlock = "";
string logV45PreEntryHighSignals = "";
string logV452LowMicroscopeActive = "";
string logV452LowFinalPath = "";
string logV452LowEntryRoute = "";
string logV452LowRecoveryProfile = "";
string logV452LowFav1ToFav3Delta = "";
string logV452LowFav2ToFav3Delta = "";
string logV452LowMaxFav1To3 = "";
string logV452LowHad1sAdverseJump = "";
string logV452LowHad2sAdverseJump = "";
string logV452LowJumpRecoveredBy3s = "";
string logV452LowJumpRecoveredToSpeed = "";
string logV452LowPressureActionable = "";
string logV452LowPressureBefore3s = "";
string logV452LowEscapeReason = "";
string logV452LowKillRiskFlag = "";
string logV452LowDeadStrict = "";
string logV46LowDeadShadowFired = "";
long   logV46LowDeadShadowMs = 0;
double logV46LowDeadShadowFav = 0.0;
double logV46LowDeadShadowMfe = 0.0;
double logV46LowDeadShadowMaxFav1To3 = 0.0;
double logV46LowDeadShadowReplayDelta = 0.0;
long   logV46LowDeadShadowLeadMs = 0;
string logV46LowDeadShadowBeforeCurrentShield = "";
string logV46LowDeadShadowFinalPath = "";
string logV46LowDeadShadowSpeedTouched = "";
string logV46LowDeadShadowReason = "";
string logV461FavAt250ms = "";
string logV461FavAt500ms = "";
string logV461TimeToFirstProfitMs = "";
string logV461TimeToMfe10Ms = "";
string logV461TimeToMfe20Ms = "";
string logV461TimeToMfe40Ms = "";
string logV461MfeSlope1sTo3s = "";
string logV461MaxPullbackAfterFirstProfit = "";
string logV461HighMidMicroClass = "";
string logV461HighMidTimeToSpeedMs = "";
string logV461HighMidFailedReason = "";
string logV461LowDetectMs = "";
string logV461LowDetectFav = "";
string logV461LowDetectSpread = "";
string logV461LowDetectOrderflowState = "";
string logV461LowDetectPressureState = "";
string logV461OppAtEntryMfe = "";
string logV461OppAtEntryMae = "";
string logV461OppAtEntryWouldSpeed = "";
string logV461OppAtEntryNetDelta = "";
string logV461OppAtLowMfe = "";
string logV461OppAtLowMae = "";
string logV461OppAtLowWouldSpeed = "";
string logV461OppAtLowWouldHardLose = "";
string logV461OppAtLowNetDelta = "";
string logV461LowMicroClass = "";
string logV461LowMicroClassReason = "";

string logV47BucketPresent = "";
string logV47BucketNullReason = "";
string logV47BucketAuditCloseReason = "";
string logV47BucketAuditRoute = "";
string logV47BucketAuditSession = "";
string logV47BucketAuditSpread = "";
string logV47BucketAuditFinalPath = "";
string logV47EntryAvoidShadow = "";
string logV47500msAvoidShadow = "";
string logV471sAvoidShadow = "";
string logV472sAvoidShadow = "";
string logV473sAvoidShadow = "";
string logV47FirstAvoidTimeMs = "";
string logV47FirstAvoidStage = "";
string logV47AvoidReason = "";
string logV47AvoidReplayDelta = "";
string logV47WouldBlockLowNoTrade = "";
string logV47WouldBlockLowUnresolved = "";
string logV47WouldBlockHigh = "";
string logV47WouldBlockMid = "";
string logV47WouldBlockSpeed = "";
string logV47PreEntryShadowScore = "";
string logV47PreEntryShadowBucket = "";
string logV47PreEntryShadowSignals = "";
string logV47TimeToFirstFavorableTickMs = "";
string logV47First500msAdverseJump = "";
string logV47First1sAdverseJump = "";
string logV47First2sAdverseJump = "";
string logV47FrontierNotes = "";

string logV471SchemaVersion = "";
string logV471RouteScope = "";
string logV471Alive100ms = "";
string logV471Alive250ms = "";
string logV471Alive500ms = "";
string logV471Alive750ms = "";
string logV471Alive1s = "";
string logV471Alive1500ms = "";
string logV471Alive2s = "";
string logV471Alive3s = "";
string logV471Sample100ms = "";
string logV471Sample250ms = "";
string logV471Sample500ms = "";
string logV471Sample750ms = "";
string logV471Sample1s = "";
string logV471Sample1500ms = "";
string logV471Sample2s = "";
string logV471Sample3s = "";
string logV471Fav100ms = "";
string logV471Fav250ms = "";
string logV471Fav500ms = "";
string logV471Fav750ms = "";
string logV471Fav1s = "";
string logV471Fav1500ms = "";
string logV471Fav2s = "";
string logV471Fav3s = "";
string logV471Ticks100ms = "";
string logV471Ticks250ms = "";
string logV471Ticks500ms = "";
string logV471Ticks750ms = "";
string logV471Ticks1s = "";
string logV471Ticks1500ms = "";
string logV471Ticks2s = "";
string logV471Ticks3s = "";
string logV471First250msAdverseJump = "";
string logV471First500msAdverseJump = "";
string logV471First750msAdverseJump = "";
string logV471First1sAdverseJump = "";
string logV471First2sAdverseJump = "";
string logV471TickPath1to8 = "";
string logV471PreEntryTapeHealth = "";
string logV471PreEntryVelocityDecay = "";
string logV471PreSpeedSignalAgeMs = "";
string logV471FirstFavorableTickState = "";
string logV471EntryAvoidShadow = "";
string logV471250msAvoidShadow = "";
string logV471500msAvoidShadow = "";
string logV471750msAvoidShadow = "";
string logV4711sAvoidShadow = "";
string logV471FirstAvoidTimeMs = "";
string logV471FirstAvoidStage = "";
string logV471AvoidReason = "";
string logV471AvoidReplayDelta = "";
string logV471WouldBlockLowNoTrade = "";
string logV471WouldBlockLowUnresolved = "";
string logV471WouldBlockHigh = "";
string logV471WouldBlockMid = "";
string logV471WouldBlockSpeed = "";
string logV471CoverageNote = "";
string logV48Mode2Signal = "";
string logV48Mode2BlockReason = "";
string logV48Mode2WouldAllow = "";
string logV48Mode2WouldBlock = "";
string logV48Mode2OppFlags = "";
string logV48Mode2Velocity1s = "";
string logV48Mode2WeightFactor = "";
double logBidAtRequest = 0.0;
double logAskAtRequest = 0.0;
double logSpreadAtRequest = 0.0;
double logVelocity1s = 0.0;
double logVelocity3s = 0.0;
double logVelocity5s = 0.0;
uint   logTradeRetcode = 0;

long   lastVisualSpeedMs = 0;
double lastVisualSpeedPrice = 0.0;
int    speedVisualCounter = 0;
string lastCapSkipReason = "";
datetime lastCapSkipTime = 0;
uint   lastCloseRetcode = 0;
string lastCloseRetcodeDescription = "";
const string SAR_LIFECYCLE_RUN_TAG = "SAR_ROUTER_LIFECYCLE_V2";
ulong  logLifecyclePositionTicket = 0;
string logLifecycleCloseMechanism = "";
double logLifecycleClosePrice = 0.0;
long   logLifecycleCloseServerTimeMsc = 0;
ulong  logLifecycleClosingDealTicket = 0;
int    defensiveCloseStreak = 0;
long   defensiveLockoutUntilMs = 0;
long   defensiveLockoutLastLogMs = 0;
long   aiShadowCurrentEntrySecondMs = 0;
long   aiShadowPriorEntrySecondMs = 0;

const uint SAR_RETCODE_CLOSE_ORDER_EXISTS = 10039;
const uint SAR_RETCODE_POSITION_CLOSED = 10036;
const uint SAR_RETCODE_FROZEN = 10029;

//+------------------------------------------------------------------+
// Separate opt-in continuation candidate.
#include "ContinuationRuntime.mqh"
#include "ContinuationExecution.mqh"
#include "SpeedTrailRuntime.mqh"

int OnInit()
{
#ifdef SAR_CAPTURE_SMOKE
   if(!MQLInfoInteger(MQL_TESTER)) return INIT_FAILED;
#endif
   sarCaptureEffectiveHash=SARCaptureSHA256(SARCaptureEffectiveCanonical());
   SARCaptureWriteInit();
   if(!CGInit()) return INIT_PARAMETERS_INCORRECT;
   if(UseCandleEntryFilter && EntryRouterMode==StopOnly)
   {
      Print("CANDLE_GATE_INIT requires StopAndMarket or StopMarketLimit; StopOnly has no eligible market entries");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(!SRTInit()) return INIT_PARAMETERS_INCORRECT;
   if(!CFRInit()) return INIT_FAILED;
   if(!CP_Init())
      return INIT_PARAMETERS_INCORRECT;
   ArrayResize(exitProfitGateStates, 0);
   ArrayResize(burstSettleStates, 0);
   if(!ValidateBurstSettleInputs())
      return INIT_PARAMETERS_INCORRECT;
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(SlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);
   if(!ValidateTrailLayerInputs())
      return INIT_FAILED;
   if(!ValidateAndLogSymbolCalibration())
      return INIT_FAILED;
   GateStackWriteHeader();
   TrailLayerWriteHeader();
   if(InpUseExitReasonAudit)
      AuditExitReasonConfiguration();
   EventSetTimer(1);
   if(SpeedVisualCleanOldOnInit)
      SpeedVisualDeleteAll();
   WriteHeader();
   SarOrderFlowDecisionWriteHeader();
   AIDecisionAttemptWriteHeader();
   AIShadowWriteHeader();
   AIPreEntryJourneyWriteHeader();
   AIJourneyShadowWriteHeader();
   AIT200ShadowWriteHeader();
   AIShadowRestoreEntryClock();
   if(InpAIHardGateEnabled || InpAIRiskAdjustEnabled)
      Print("AI Stage 1 warning: hard-gate and risk-adjust inputs are recorded only and have no execution authority.");
   Print("SpeedAlert DirectionRouter test EA loaded. MaxTrailingMultiplier is alarm only.");
   Print("EXIT_GATE_68 v1.494: EA close rules resume after first profit above 6.8 pips; broker SL/TP remain active.");
   PrintFormat("BURST_SETTLE_1494 enabled=%s quiet_ms=%d speed_fraction=%.2f cap_pips_sec=%.2f pullback_pips=%.2f; delays trailing SL modifications only",
               (InpWaitForBurstSettle ? "true" : "false"), InpBurstSettleQuietMs,
               InpBurstSettleSpeedFraction, InpBurstSettleMaxSpeedPipsSec,
               InpBurstSettlePullbackPips);
   // XPDIR: DIR_OFF creates no indicator handle and reads nothing.
   if(!XPDir_Init(MagicNumber))
      return INIT_FAILED;

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
#ifdef SAR_CAPTURE_SMOKE
   SARCaptureSmokeRestore();
#endif
   XPDir_Deinit();          // XPDIR: IndicatorRelease on every rung handle
   CP_Deinit();
   CGDeinit();
   AIT200ShadowCensorAll("CENSORED_EA_DEINIT");
   EventKillTimer();
   if(SpeedVisualDeleteOnDeinit)
      SpeedVisualDeleteAll();
}

//+------------------------------------------------------------------+
void OnTick()
{
#ifdef SAR_CAPTURE_SMOKE
   SARCaptureSmokeTick();
   return;
#endif
   CGOnTick();
   CP_OnTick();
   CGCancelPendings(trade, MagicNumber);
   if(TradingEnabled)
      CP_RecheckPendings(trade, MagicNumber);
   MqlTick t;
   if(!SymbolInfoTick(_Symbol, t))
      return;

   SARCaptureQuoteRetrieved(t);
   double mid = (t.bid + t.ask) * 0.5;
   double spreadPts = (t.ask - t.bid) / _Point;
   StoreTick(t.time_msc, mid, spreadPts);
   UpdateSpeedAlert(t, mid, spreadPts);

   ManagePendingExpiry();
   CFRReconcile();
   ManagePosition(t);
   UpdateV44FOLMSGhosts(t);
   AIT200ShadowUpdate(t);

   if(!speedActive)
   {
      if(entryHoldArmed)
         ResetEntryHoldCandidate();
      return;
   }

   if(SkipEntryForDefensiveLockout())
      return;

   if(InpUseEntryHold && entryHoldArmed)
   {
      ProcessArmedEntryHold(t);
      return;
   }

   DirectionState s;
   BuildDirectionState(t, s);

   RouterAction action = DecideAction(s);
   int side = WinnerSide(s);
   bool stopWithBodyAgainst = ((action == ActBuyStop || action == ActSellStop) &&
                               side != 0 &&
                               s.bodyDir != 0 &&
                               s.bodyDir == -side);
   if(stopWithBodyAgainst)
   {
      LogDecision("SKIP_" + ActionName(action), action, s, "body_not_with_trade_stop_blocked", 0.0, 0.0, 0.0, 0.0);
      return;
   }

   if(action == ActSkip)
   {
      LogDecision("SKIP", action, s, "direction_mixed_or_not_confirmed", 0.0, 0.0, 0.0, 0.0);
      return;
   }

   int actionSide = ActionSide(action);
   if(InpUseEntryHold)
   {
      GateDecisionSnapshot preEntryGateSnapshot;
      CaptureGateDecisionSnapshot(action, actionSide, t, mid,
                                  preEntryGateSnapshot);
      if(EntryHoldFailureCurrentBar())
      {
         LogEntryHoldDecision("BLOCKED_SAME_M1", action, actionSide, t,
                              t.time_msc, mid, 0, 0.0, 1, 0);
         GateStackLogEntryDecision(preEntryGateSnapshot,
                                   "PRE_ENTRY_HOLD_BLOCKED_SAME_M1",
                                   0, 0);
         speedActive = false;
         return;
      }
      ArmEntryHold(action, actionSide, t, mid, s);
      GateStackLogEntryDecision(preEntryGateSnapshot,
                                "PRE_ENTRY_HOLD_ARMED", 0, 0);
      return;
   }

   double prior60DriftPoints = 0.0;
   if(InpUsePrior60Filter)
   {
      LogEntryHoldDecision("BYPASS", action, actionSide, t,
                           t.time_msc, mid, 0, 0.0, 0, 0);
      if(!EntryPrior60Approved(action, actionSide, t, mid, 0.0,
                               prior60DriftPoints))
      {
         GateDecisionSnapshot prior60VetoSnapshot;
         CaptureGateDecisionSnapshot(action, actionSide, t, mid,
                                     prior60VetoSnapshot);
         GateStackLogEntryDecision(prior60VetoSnapshot, "VETO", 0, 0);
         speedActive = false;
         return;
      }
   }

   GateDecisionSnapshot gateSnapshot;
   CaptureGateDecisionSnapshot(action, actionSide, t, mid, gateSnapshot);
   if(!GateDecisionAllowsEntry(gateSnapshot))
   {
      GateStackLogEntryDecision(gateSnapshot, "VETO", 0, 0);
      speedActive = false;
      return;
   }

   string scenarioKey = ScenarioKeyForAction(action, s);
   if(!ScenarioCanPlace(scenarioKey, action, s))
   {
      if(!InpUsePrior60Filter)
      {
         LogEntryHoldDecision("BYPASS", action, actionSide, t,
                              t.time_msc, mid, 0, 0.0, 0, 0);
         EntryPrior60Approved(action, actionSide, t, mid, 0.0,
                              prior60DriftPoints);
      }
      GateStackLogEntryDecision(gateSnapshot, "CAP_SKIP", 0, 0);
      return;
   }

   if(CancelOldPendings)
   {
      if(ScenarioIndependentPerformance && CancelOnlySameScenarioPendings)
         CancelPendingsForScenario(scenarioKey, "new_same_scenario_decision");
      else
         CancelPendings("new_speed_router_decision");
   }

   bool placed = PlaceAction(action, t, s);
   if(!InpUsePrior60Filter)
   {
      LogEntryHoldDecision("BYPASS", action, actionSide, t,
                           t.time_msc, mid, 0, 0.0, 0, 0);
      EntryPrior60Approved(action, actionSide, t, mid, 0.0,
                           prior60DriftPoints);
   }
   GateStackLogEntryDecision(gateSnapshot,
                             placed ? "PLACED" : "PLACE_FAILED",
                             placed ? trade.ResultOrder() : 0,
                             placed ? CurrentPositionIdentifier() : 0);
   speedActive = false;
}

//+------------------------------------------------------------------+
void OnTimer()
{
#ifdef SAR_CAPTURE_SMOKE
   return;
#endif
   XPDir_FunnelHeartbeat();   // XPDIR: explains a silent ladder in the log
   CGCancelPendings(trade, MagicNumber);
   if(TradingEnabled)
      CP_RecheckPendings(trade, MagicNumber);
   MqlTick t;
   if(!SymbolInfoTick(_Symbol, t))
      return;
   ManagePendingExpiry();
   CFRReconcile();
   ManagePosition(t);
}

//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   CFRReconcile();
   if((!InpUseSlippageInstrumentation && !InpUseExitReasonAudit) ||
      trans.type != TRADE_TRANSACTION_DEAL_ADD || trans.deal == 0)
      return;

   if(!HistoryDealSelect(trans.deal))
      return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol ||
      HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != MagicNumber)
      return;

   ENUM_DEAL_ENTRY entryType =
      (ENUM_DEAL_ENTRY)HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   bool isEntry = (entryType == DEAL_ENTRY_IN || entryType == DEAL_ENTRY_INOUT);
   bool isExit = (entryType == DEAL_ENTRY_OUT ||
                  entryType == DEAL_ENTRY_OUT_BY ||
                  entryType == DEAL_ENTRY_INOUT);
   if(!isEntry && !isExit)
      return;

   ENUM_DEAL_TYPE dealType =
      (ENUM_DEAL_TYPE)HistoryDealGetInteger(trans.deal, DEAL_TYPE);
   int side = (dealType == DEAL_TYPE_BUY ? 1 : -1);
   if(isExit && !isEntry)
      side = -side;

   double actualPrice = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   double requestedPrice = 0.0;
   ulong orderTicket = (ulong)HistoryDealGetInteger(trans.deal, DEAL_ORDER);
   if(orderTicket > 0 && HistoryOrderSelect(orderTicket))
      requestedPrice = HistoryOrderGetDouble(orderTicket, ORDER_PRICE_OPEN);

   long dealReason = HistoryDealGetInteger(trans.deal, DEAL_REASON);
   if(isExit && dealReason == DEAL_REASON_SL)
      requestedPrice = HistoryDealGetDouble(trans.deal, DEAL_SL);
   else if(isExit && dealReason == DEAL_REASON_TP)
      requestedPrice = HistoryDealGetDouble(trans.deal, DEAL_TP);
   if(requestedPrice <= 0.0 && request.price > 0.0)
      requestedPrice = request.price;

   double signedSlippagePoints = 0.0;
   double adverseSlippagePoints = 0.0;
   if(requestedPrice > 0.0 && actualPrice > 0.0 && side != 0)
   {
      signedSlippagePoints = (actualPrice - requestedPrice) / _Point;
      adverseSlippagePoints = (isExit && !isEntry
                               ? (side > 0
                                  ? requestedPrice - actualPrice
                                  : actualPrice - requestedPrice)
                               : (side > 0
                                  ? actualPrice - requestedPrice
                                  : requestedPrice - actualPrice)) / _Point;
   }

   MqlTick tick;
   double entrySpeed = 0.0;
   if(isEntry && SymbolInfoTick(_Symbol, tick))
   {
      double mid = (tick.bid + tick.ask) * 0.5;
      entrySpeed = MathAbs(SignedVelocityPointsPerSecond(mid, tick.time_msc, 1000));
   }

   string dealComment = HistoryDealGetString(trans.deal, DEAL_COMMENT);
   string details = StringFormat(
      "phase=%s deal=%I64u order=%I64u requested_price=%.10f actual_price=%.10f requested_available=%d signed_slippage_points=%.1f adverse_slippage_points=%.1f entry_speed_1s_points_per_sec=%.1f alert_speed_points=%.1f deal_reason=%d deal_comment=%s retcode=%u",
      (isEntry && isExit ? "INOUT" : (isEntry ? "ENTRY" : "EXIT")),
      trans.deal, orderTicket, requestedPrice, actualPrice,
      requestedPrice > 0.0 ? 1 : 0, signedSlippagePoints,
      adverseSlippagePoints, entrySpeed, speedPoints,
      (int)dealReason, dealComment, result.retcode);
   ExecutionAuditWrite("FILL", side, details);
}

//+------------------------------------------------------------------+
datetime CurrentEntryM1Bar()
{
   return iTime(_Symbol, PERIOD_M1, 0);
}

//+------------------------------------------------------------------+
void ResetEntryHoldCandidate()
{
   entryHoldArmed = false;
   entryHoldSignalMs = 0;
   entryHoldSignalMid = 0.0;
   entryHoldSignalBar = 0;
   entryHoldAction = ActSkip;
   ResetState(entryHoldDirectionState);
}

//+------------------------------------------------------------------+
bool EntryHoldFailureCurrentBar()
{
   datetime bar = CurrentEntryM1Bar();
   return (bar > 0 && entryHoldFailedBar == bar);
}

//+------------------------------------------------------------------+
string SpeedThresholdAuditDetails()
{
   return StringFormat("speed_mode=%s speed_gate_value=%.1f speed_threshold=%.1f speed_window_samples=%d speed_percentile=%.2f current_sample_excluded=1",
                       (InpSpeedThresholdMode == FIXED ? "FIXED" : "PERCENTILE"),
                       lastSpeedGateValue, lastSpeedComputedThreshold,
                       lastSpeedThresholdSamples, InpSpeedPercentile);
}

//+------------------------------------------------------------------+
void LogEntryHoldDecision(const string status,
                          const RouterAction action,
                          const int side,
                          const MqlTick &t,
                          const long signalMs,
                          const double signalMid,
                          const long elapsedMs,
                          const double holdMovePoints,
                          const int entryHoldFailed,
                          const int prior60Failed)
{
   double currentMid = (t.bid + t.ask) * 0.5;
   string details = StringFormat(
      "gate=ENTRY_HOLD action=%s enabled=%d status=%s signal_time_msc=%I64d signal_mid=%.10f current_mid=%.10f elapsed_ms=%I64d required_ms=%d hold_move_points=%.1f required_move_points=%.1f pass=%d entry_hold_failed=%d prior60_failed=%d %s",
      ActionName(action), InpUseEntryHold ? 1 : 0, status,
      signalMs, signalMid, currentMid, elapsedMs, InpEntryHoldMs,
      holdMovePoints, InpEntryHoldMinFavPoints,
      (status == "PASS" || status == "BYPASS") ? 1 : 0,
      entryHoldFailed, prior60Failed, SpeedThresholdAuditDetails());
   ExecutionAuditWrite("ENTRY_GATE", side, details);
}

//+------------------------------------------------------------------+
bool MeasurePrior60Drift(const long tickTimeMsc,
                         const double midPrice,
                         double &driftPoints,
                         long &sampleTimeMsc)
{
   driftPoints = 0.0;
   sampleTimeMsc = 0;
   const long lookbackMsc = 60 * 60 * 1000;
   if(_Point <= 0.0 || tickTimeMsc <= lookbackMsc)
      return false;

   long targetTimeMsc = tickTimeMsc - lookbackMsc;
   ulong fromTimeMsc = (ulong)MathMax(0, targetTimeMsc - 5000);
   ulong toTimeMsc = (ulong)(targetTimeMsc + 5000);
   MqlTick priorTicks[];
   int copied = CopyTicksRange(_Symbol, priorTicks, COPY_TICKS_ALL,
                               fromTimeMsc, toTimeMsc);
   if(copied <= 0)
      return false;

   long bestDeltaMsc = 0;
   double priorMid = 0.0;
   for(int i = 0; i < copied; i++)
   {
      if(priorTicks[i].bid <= 0.0 || priorTicks[i].ask <= 0.0 ||
         priorTicks[i].time_msc <= 0)
         continue;
      long deltaMsc = (long)MathAbs((double)(priorTicks[i].time_msc -
                                             targetTimeMsc));
      if(sampleTimeMsc == 0 || deltaMsc < bestDeltaMsc)
      {
         bestDeltaMsc = deltaMsc;
         sampleTimeMsc = priorTicks[i].time_msc;
         priorMid = (priorTicks[i].bid + priorTicks[i].ask) * 0.5;
      }
   }
   if(sampleTimeMsc == 0 || priorMid <= 0.0)
      return false;

   driftPoints = (midPrice - priorMid) / _Point;
   return true;
}

//+------------------------------------------------------------------+
bool EntryPrior60Approved(const RouterAction action,
                          const int side,
                          const MqlTick &t,
                          const double midPrice,
                          const double holdMovePoints,
                          double &driftPoints)
{
   long sampleTimeMsc = 0;
   bool available = MeasurePrior60Drift(t.time_msc, midPrice,
                                        driftPoints, sampleTimeMsc);
   bool directionPassed = (available && side != 0 &&
                           ((side > 0 && driftPoints > 0.0) ||
                            (side < 0 && driftPoints < 0.0)));
   bool passed = (!InpUsePrior60Filter || directionPassed);
   long sampledLookbackMs = (sampleTimeMsc > 0
                             ? t.time_msc - sampleTimeMsc : 0);
   int failed = (InpUsePrior60Filter && !directionPassed ? 1 : 0);
   string details = StringFormat(
      "gate=PRIOR60 action=%s enabled=%d status=%s lookback_min=60 drift_available=%d prior60_drift_points=%.1f side_oriented_drift_points=%.1f sampled_lookback_ms=%I64d hold_move_points=%.1f pass=%d entry_hold_failed=0 prior60_failed=%d %s",
      ActionName(action), InpUsePrior60Filter ? 1 : 0,
      (InpUsePrior60Filter ? (passed ? "PASS" : "FAIL") : "BYPASS"),
      available ? 1 : 0, driftPoints, driftPoints * side,
      sampledLookbackMs, holdMovePoints, passed ? 1 : 0, failed,
      SpeedThresholdAuditDetails());
   ExecutionAuditWrite("ENTRY_GATE", side, details);
   return passed;
}

//+------------------------------------------------------------------+
string SarBool(const bool value)
{
   return value ? "true" : "false";
}

//+------------------------------------------------------------------+
string SarAvailableDouble(const bool available,
                          const double value,
                          const int digits = 3)
{
   return available ? DoubleToString(value, digits) : "UNAVAILABLE";
}

//+------------------------------------------------------------------+
string SarWouldVeto(const bool available, const bool passed)
{
   return available ? SarBool(!passed) : "UNAVAILABLE";
}

//+------------------------------------------------------------------+
string BurstThresholdModeName()
{
   return InpBurstThresholdMode == FIXED ? "FIXED" : "PERCENTILE";
}

//+------------------------------------------------------------------+
void CaptureGateDecisionSnapshot(const RouterAction action,
                                 const int side,
                                 const MqlTick &t,
                                 const double mid,
                                 GateDecisionSnapshot &snapshot)
{
   gateDecisionSequence++;
   snapshot.decisionId = gateDecisionSequence;
   snapshot.timeMsc = t.time_msc;
   snapshot.action = action;
   snapshot.side = side;
   snapshot.burstAvailable = lastBurstAvailable;
   snapshot.burstSignedPoints = lastBurstSignedPoints;
   snapshot.burstAbsPoints = lastBurstAbsPoints;
   snapshot.burstThresholdAvailable = lastBurstThresholdAvailable;
   snapshot.burstThresholdPoints = lastBurstResolvedThreshold;
   snapshot.burstThresholdSamples = lastBurstThresholdSamples;
   snapshot.burstPass = (snapshot.burstAvailable &&
                         snapshot.burstThresholdAvailable &&
                         snapshot.burstAbsPoints >= snapshot.burstThresholdPoints &&
                         ((side > 0 && snapshot.burstSignedPoints > 0.0) ||
                          (side < 0 && snapshot.burstSignedPoints < 0.0)));

   long sampleTimeMsc = 0;
   snapshot.friendlyAvailable = MeasurePrior60Drift(t.time_msc, mid,
                                                     snapshot.friendly60DriftPoints,
                                                     sampleTimeMsc);
   snapshot.friendlyPass = (snapshot.friendlyAvailable && side != 0 &&
                            ((side > 0 && snapshot.friendly60DriftPoints > 0.0) ||
                             (side < 0 && snapshot.friendly60DriftPoints < 0.0)));
}

//+------------------------------------------------------------------+
bool GateDecisionAllowsEntry(const GateDecisionSnapshot &snapshot)
{
   if(InpUseHighBurstGate && !snapshot.burstPass)
      return false;
   if(InpUsePrior60Filter && !snapshot.friendlyPass)
      return false;
   return true;
}

//+------------------------------------------------------------------+
ulong CurrentPositionIdentifier()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == MagicNumber)
         return (ulong)PositionGetInteger(POSITION_IDENTIFIER);
   }
   return 0;
}

//+------------------------------------------------------------------+
void GateStackWriteHeader()
{
   int h = FileOpen(SAR_GATE_STACK_FILE,
                    FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI |
                    FILE_SHARE_READ | FILE_SHARE_WRITE, ",");
   if(h == INVALID_HANDLE)
   {
      if(!gateFileErrorLogged)
      {
         Print("SAR_GATE_STACK_FILE_OPEN_FAILED error=", GetLastError());
         gateFileErrorLogged = true;
      }
      return;
   }
   if(FileSize(h) == 0)
      FileWrite(h, "schema_version", "row_kind", "decision_id",
                "time_msc", "symbol", "magic", "action", "side",
                "outcome", "burst_value_pts", "burst_signed_pts",
                "burst_threshold_pts", "burst_threshold_samples",
                "burst_pass", "burst_would_have_vetoed", "burst_mode",
                "burst_enabled", "hold_value_pts", "hold_pass",
                "hold_would_have_vetoed", "hold_mode", "hold_enabled",
                "hold_elapsed_ms",
                "friendly60_drift_pts", "friendly60_pass",
                "friendly60_would_have_vetoed", "friendly60_mode",
                "friendly60_enabled", "pre_entry_hold_enabled",
                "pre_entry_hold_value_pts", "pre_entry_hold_pass",
                "pre_entry_hold_would_have_vetoed", "pre_entry_hold_mode",
                "order_ticket", "position_id", "saved_vs_forfeited",
                "close_sent", "close_retcode");
   FileClose(h);
}

//+------------------------------------------------------------------+
void GateStackLogEntryDecision(const GateDecisionSnapshot &snapshot,
                               const string outcome,
                               const ulong orderTicket,
                               const ulong positionId,
                               const bool preEntryHoldAvailable = false,
                               const double preEntryHoldValue = 0.0,
                               const bool preEntryHoldPass = false)
{
   int h = FileOpen(SAR_GATE_STACK_FILE,
                    FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI |
                    FILE_SHARE_READ | FILE_SHARE_WRITE, ",");
   if(h == INVALID_HANDLE)
   {
      if(!gateFileErrorLogged)
      {
         Print("SAR_GATE_STACK_FILE_OPEN_FAILED error=", GetLastError());
         gateFileErrorLogged = true;
      }
      return;
   }
   FileSeek(h, 0, SEEK_END);
   bool burstDecisionAvailable = (snapshot.burstAvailable &&
                                  snapshot.burstThresholdAvailable);
   FileWrite(h, "sar.gatestack.v1", "ENTRY_DECISION",
             (string)snapshot.decisionId, (string)snapshot.timeMsc,
             _Symbol, (string)MagicNumber, ActionName(snapshot.action),
             snapshot.side > 0 ? "BUY" : "SELL", outcome,
             SarAvailableDouble(snapshot.burstAvailable,
                                snapshot.burstAbsPoints),
             SarAvailableDouble(snapshot.burstAvailable,
                                snapshot.burstSignedPoints),
             SarAvailableDouble(snapshot.burstThresholdAvailable,
                                snapshot.burstThresholdPoints),
             (InpBurstThresholdMode == PERCENTILE
              ? (string)snapshot.burstThresholdSamples : "0"),
             burstDecisionAvailable ? SarBool(snapshot.burstPass) : "UNAVAILABLE",
             SarWouldVeto(burstDecisionAvailable, snapshot.burstPass),
             BurstThresholdModeName(), SarBool(InpUseHighBurstGate),
              "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE",
              "POST_FILL_1000MS", SarBool(InpUse1000msHold),
              "UNAVAILABLE",
              SarAvailableDouble(snapshot.friendlyAvailable,
                                snapshot.friendly60DriftPoints),
             snapshot.friendlyAvailable ? SarBool(snapshot.friendlyPass) :
                                           "UNAVAILABLE",
              SarWouldVeto(snapshot.friendlyAvailable, snapshot.friendlyPass),
              "SIGNED_60M_MID", SarBool(InpUsePrior60Filter),
              SarBool(InpUseEntryHold),
              SarAvailableDouble(preEntryHoldAvailable, preEntryHoldValue),
              preEntryHoldAvailable ? SarBool(preEntryHoldPass) : "UNAVAILABLE",
              SarWouldVeto(preEntryHoldAvailable, preEntryHoldPass),
              "PRE_ENTRY_CONFIRMATION",
              orderTicket > 0 ? (string)orderTicket : "UNAVAILABLE",
              positionId > 0 ? (string)positionId : "UNAVAILABLE",
              "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE");
   FileClose(h);
}

//+------------------------------------------------------------------+
void GateStackLogPostFillHold(const GateDecisionSnapshot &snapshot,
                              const ulong ticket,
                              const ulong positionId,
                              const long elapsedMs,
                              const double favourablePoints,
                              const bool holdPassed,
                              const string outcome,
                              const string savedVsForfeited,
                              const bool closeSent,
                              const uint closeRetcode)
{
   int h = FileOpen(SAR_GATE_STACK_FILE,
                    FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI |
                    FILE_SHARE_READ | FILE_SHARE_WRITE, ",");
   if(h == INVALID_HANDLE)
   {
      if(!gateFileErrorLogged)
      {
         Print("SAR_GATE_STACK_FILE_OPEN_FAILED error=", GetLastError());
         gateFileErrorLogged = true;
      }
      return;
   }

   FileSeek(h, 0, SEEK_END);
   bool burstDecisionAvailable = (snapshot.burstAvailable &&
                                  snapshot.burstThresholdAvailable);
   FileWrite(h, "sar.gatestack.v1", "POST_FILL_HOLD",
             (string)snapshot.decisionId, (string)snapshot.timeMsc,
             _Symbol, (string)MagicNumber, ActionName(snapshot.action),
             snapshot.side > 0 ? "BUY" : "SELL", outcome,
             SarAvailableDouble(snapshot.burstAvailable,
                                snapshot.burstAbsPoints),
             SarAvailableDouble(snapshot.burstAvailable,
                                snapshot.burstSignedPoints),
             SarAvailableDouble(snapshot.burstThresholdAvailable,
                                snapshot.burstThresholdPoints),
             (InpBurstThresholdMode == PERCENTILE
              ? (string)snapshot.burstThresholdSamples : "0"),
             burstDecisionAvailable ? SarBool(snapshot.burstPass) : "UNAVAILABLE",
             SarWouldVeto(burstDecisionAvailable, snapshot.burstPass),
             BurstThresholdModeName(), SarBool(InpUseHighBurstGate),
             DoubleToString(favourablePoints, 3), SarBool(holdPassed),
             SarBool(!holdPassed),
             "POST_FILL_1000MS",
             SarBool(InpUse1000msHold),
             (string)elapsedMs,
             SarAvailableDouble(snapshot.friendlyAvailable,
                                snapshot.friendly60DriftPoints),
             snapshot.friendlyAvailable ? SarBool(snapshot.friendlyPass) :
                                           "UNAVAILABLE",
             SarWouldVeto(snapshot.friendlyAvailable, snapshot.friendlyPass),
             "SIGNED_60M_MID", SarBool(InpUsePrior60Filter),
             SarBool(InpUseEntryHold),
             "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE",
             "PRE_ENTRY_CONFIRMATION",
             "UNAVAILABLE",
             positionId > 0 ? (string)positionId : "UNAVAILABLE",
             savedVsForfeited, SarBool(closeSent),
             closeRetcode > 0 ? (string)closeRetcode : "UNAVAILABLE");
   FileClose(h);
}

//+------------------------------------------------------------------+
void ArmEntryHold(const RouterAction action,
                  const int side,
                  const MqlTick &t,
                  const double mid,
                  const DirectionState &state)
{
   entryHoldArmed = true;
   entryHoldSignalMs = t.time_msc;
   entryHoldSignalMid = mid;
   entryHoldSignalBar = CurrentEntryM1Bar();
   entryHoldAction = action;
   entryHoldDirectionState = state;
   LogEntryHoldDecision("ARMED", action, side, t,
                        entryHoldSignalMs, entryHoldSignalMid,
                        0, 0.0, 0, 0);
}

//+------------------------------------------------------------------+
void ProcessArmedEntryHold(const MqlTick &t)
{
   if(!entryHoldArmed || entryHoldAction == ActSkip)
      return;

   long elapsedMs = t.time_msc - entryHoldSignalMs;
   if(elapsedMs < 0)
      elapsedMs = 0;
   if(elapsedMs < (long)MathMax(0, InpEntryHoldMs))
      return;

   int side = ActionSide(entryHoldAction);
   double currentMid = (t.bid + t.ask) * 0.5;
   double holdMovePoints = (side > 0
                            ? currentMid - entryHoldSignalMid
                            : entryHoldSignalMid - currentMid) / _Point;
   bool passed = (side != 0 &&
                  holdMovePoints >= InpEntryHoldMinFavPoints);
   RouterAction action = entryHoldAction;
   DirectionState state = entryHoldDirectionState;
   long signalMs = entryHoldSignalMs;
   double signalMid = entryHoldSignalMid;
   datetime signalBar = entryHoldSignalBar;

   LogEntryHoldDecision(passed ? "PASS" : "FAIL", action, side, t,
                        signalMs, signalMid, elapsedMs,
                        holdMovePoints, passed ? 0 : 1, 0);
   GateDecisionSnapshot gateSnapshot;
   CaptureGateDecisionSnapshot(action, side, t, currentMid, gateSnapshot);
   if(!passed)
   {
      GateStackLogEntryDecision(gateSnapshot, "PRE_ENTRY_HOLD_VETO",
                                0, 0, true, holdMovePoints, false);
      datetime failureBar = CurrentEntryM1Bar();
      entryHoldFailedBar = (failureBar > 0 ? failureBar : signalBar);
      ResetEntryHoldCandidate();
      speedActive = false;
      return;
   }

   double prior60DriftPoints = 0.0;
   if(!EntryPrior60Approved(action, side, t, currentMid,
                            holdMovePoints, prior60DriftPoints))
   {
      GateStackLogEntryDecision(gateSnapshot, "VETO_AFTER_PRE_ENTRY_HOLD",
                                0, 0, true, holdMovePoints, true);
      ResetEntryHoldCandidate();
      speedActive = false;
      return;
   }

   if(!GateDecisionAllowsEntry(gateSnapshot))
   {
      GateStackLogEntryDecision(gateSnapshot, "VETO_AFTER_PRE_ENTRY_HOLD",
                                0, 0, true, holdMovePoints, true);
      ResetEntryHoldCandidate();
      speedActive = false;
      return;
   }

   string scenarioKey = ScenarioKeyForAction(action, state);
   if(!ScenarioCanPlace(scenarioKey, action, state))
   {
      GateStackLogEntryDecision(gateSnapshot,
                                "CAP_SKIP_AFTER_PRE_ENTRY_HOLD",
                                0, 0, true, holdMovePoints, true);
      ResetEntryHoldCandidate();
      return;
   }

   if(CancelOldPendings)
   {
      if(ScenarioIndependentPerformance && CancelOnlySameScenarioPendings)
         CancelPendingsForScenario(scenarioKey, "new_same_scenario_decision");
      else
         CancelPendings("new_speed_router_decision");
   }

   bool placed = PlaceAction(action, t, state);
   GateStackLogEntryDecision(gateSnapshot,
                              placed ? "PLACED_AFTER_PRE_ENTRY_HOLD" :
                                       "PLACE_FAILED_AFTER_PRE_ENTRY_HOLD",
                              placed ? trade.ResultOrder() : 0,
                              placed ? CurrentPositionIdentifier() : 0,
                              true, holdMovePoints, true);
   ResetEntryHoldCandidate();
   speedActive = false;
}

//+------------------------------------------------------------------+
void StoreTick(const long ms, const double mid, const double spreadPts)
{
   int n = ArraySize(tickMs);
   if(n <= 0)
      burstEpochStartMs = ms;
   else if(ms - tickMs[n - 1] > 1000)
   {
      burstEpochStartMs = ms;
      ArrayResize(speedOneSecondObservations, 0);
   }
   ArrayResize(tickMs, n + 1);
   ArrayResize(tickMid, n + 1);
   ArrayResize(tickSpread, n + 1);
   tickMs[n] = ms;
   tickMid[n] = mid;
   tickSpread[n] = spreadPts;

   long keepFrom = ms - 240000;
   int first = 0;
   while(first < ArraySize(tickMs) && tickMs[first] < keepFrom)
      first++;
   if(first > 256)
      CompactTicks(first);
}

//+------------------------------------------------------------------+
void CompactTicks(const int first)
{
   int oldSize = ArraySize(tickMs);
   int newSize = oldSize - first;
   if(newSize <= 0)
   {
      ArrayResize(tickMs, 0);
      ArrayResize(tickMid, 0);
      ArrayResize(tickSpread, 0);
      return;
   }
   for(int i = 0; i < newSize; i++)
   {
      tickMs[i] = tickMs[i + first];
      tickMid[i] = tickMid[i + first];
      tickSpread[i] = tickSpread[i + first];
   }
   ArrayResize(tickMs, newSize);
   ArrayResize(tickMid, newSize);
   ArrayResize(tickSpread, newSize);
}

//+------------------------------------------------------------------+
int FirstTickAtOrAfter(const long ms)
{
   int n = ArraySize(tickMs);
   for(int i = 0; i < n; i++)
      if(tickMs[i] >= ms)
         return i;
   return -1;
}

//+------------------------------------------------------------------+
double SignedVelocityPointsPerSecond(const double currentMid, const long nowMs, const int lookbackMs)
{
   int n = ArraySize(tickMs);
   if(n <= 1)
      return 0.0;

   int safeLookbackMs = MathMax(1, lookbackMs);
   int idx = FirstTickAtOrAfter(nowMs - safeLookbackMs);
   if(idx < 0)
      idx = 0;
   if(idx >= n - 1)
      idx = MathMax(0, n - 2);

   double dtSec = MathMax(0.001, (double)(nowMs - tickMs[idx]) / 1000.0);
   return ((currentMid - tickMid[idx]) / _Point) / dtSec;
}

//+------------------------------------------------------------------+
bool MeasureOneSecondBurst(const double currentMid,
                           const long nowMs,
                           double &signedBurstPoints)
{
   signedBurstPoints = 0.0;
   int n = ArraySize(tickMs);
   if(n <= 1 || _Point <= 0.0 || burstEpochStartMs <= 0 ||
      nowMs - burstEpochStartMs < 1000)
      return false;

   int idx = FirstTickAtOrAfter(nowMs - 1000);
   if(idx < 0 || idx >= n - 1 || nowMs <= tickMs[idx])
      return false;

   double dtSec = (double)(nowMs - tickMs[idx]) / 1000.0;
   if(dtSec <= 0.0)
      return false;
   signedBurstPoints = ((currentMid - tickMid[idx]) / _Point) / dtSec;
   return MathIsValidNumber(signedBurstPoints);
}

//+------------------------------------------------------------------+
int BurstObservationCapacity()
{
   int capacity = 0;
   if(InpSpeedThresholdMode == PERCENTILE)
      capacity = MathMax(capacity, MathMax(1, InpSpeedWindowSamples));
   if(InpBurstThresholdMode == PERCENTILE)
      capacity = MathMax(capacity, MathMax(1, InpBurstWindowSamples));
   return capacity;
}

//+------------------------------------------------------------------+
void AppendSpeedObservation(const double burstPoints)
{
   int window = BurstObservationCapacity();
   if(window <= 0 || !MathIsValidNumber(burstPoints))
      return;

   int n = ArraySize(speedOneSecondObservations);
   if(n >= window)
   {
      for(int i = 1; i < n; i++)
         speedOneSecondObservations[i - 1] = speedOneSecondObservations[i];
      ArrayResize(speedOneSecondObservations, n - 1);
      n--;
   }
   ArrayResize(speedOneSecondObservations, n + 1);
   speedOneSecondObservations[n] = MathAbs(burstPoints);
}

//+------------------------------------------------------------------+
double PriorBurstPercentileThreshold(const double requestedPercentile,
                                     const int requestedWindow,
                                     int &samples)
{
   int n = ArraySize(speedOneSecondObservations);
   int window = MathMax(1, requestedWindow);
   samples = MathMin(n, window);
   if(samples <= 0)
      return 0.0;

   double sorted[];
   ArrayResize(sorted, samples);
   int first = n - samples;
   for(int i = 0; i < samples; i++)
      sorted[i] = speedOneSecondObservations[first + i];
   ArraySort(sorted);
   double percentile = MathMax(0.0, MathMin(100.0, requestedPercentile));
   double rank = (percentile / 100.0) * (double)(samples - 1);
   int lower = (int)MathFloor(rank);
   int upper = (int)MathCeil(rank);
   double threshold = sorted[lower];
   if(upper > lower)
      threshold += (rank - lower) * (sorted[upper] - sorted[lower]);
   return threshold;
}

//+------------------------------------------------------------------+
void UpdateSpeedAlert(const MqlTick &t, const double mid, const double spreadPts)
{
   double priorPercentileThreshold = 0.0;
   int priorPercentileSamples = 0;
   double currentBurstPoints = 0.0;
   bool currentBurstAvailable = MeasureOneSecondBurst(mid, t.time_msc,
                                                       currentBurstPoints);
   if(InpSpeedThresholdMode == PERCENTILE)
      priorPercentileThreshold = PriorBurstPercentileThreshold(
         InpSpeedPercentile, InpSpeedWindowSamples, priorPercentileSamples);

   int burstThresholdSamples = 0;
   double burstThreshold = InpBurstThresholdPts;
   bool burstThresholdAvailable = true;
   if(InpBurstThresholdMode == PERCENTILE)
   {
      burstThreshold = PriorBurstPercentileThreshold(
         InpBurstPercentile, InpBurstWindowSamples, burstThresholdSamples);
      burstThresholdAvailable = (currentBurstAvailable &&
                                 burstThresholdSamples >= MathMax(1, InpBurstWindowSamples) &&
                                 burstThreshold > 0.0);
   }

   lastBurstAvailable = currentBurstAvailable;
   lastBurstSignedPoints = currentBurstAvailable ? currentBurstPoints : 0.0;
   lastBurstAbsPoints = currentBurstAvailable ? MathAbs(currentBurstPoints) : 0.0;
   lastBurstResolvedThreshold = burstThreshold;
   lastBurstThresholdAvailable = burstThresholdAvailable;
   lastBurstThresholdSamples = burstThresholdSamples;

   if(currentBurstAvailable)
      AppendSpeedObservation(currentBurstPoints);

   if(speedActive)
   {
      if(t.time_msc - speedStartMs > SpeedAlertHoldSeconds * 1000)
      {
         LogInfo("SPEED_ALERT_EXPIRED", "alert expired without clear direction");
         speedActive = false;
      }
      return;
   }

   int idx = FirstTickAtOrAfter(t.time_msc - SpeedLookbackSeconds * 1000);
   if(idx < 0)
      return;

   double movePts = (mid - tickMid[idx]) / _Point;
   double threshold = MathMax(MinSpeedAlertPoints, spreadPts * MaxTrailingMultiplier);
   double absMovePts = MathAbs(movePts);
   double vel1 = SignedVelocityPointsPerSecond(mid, t.time_msc, 1000);
   double vel3 = SignedVelocityPointsPerSecond(mid, t.time_msc, 3000);
   double vel5 = SignedVelocityPointsPerSecond(mid, t.time_msc, 5000);
   double gateValue = absMovePts;
   int gateDirection = (movePts > 0.0 ? 1 : -1);

   if(InpSpeedThresholdMode == PERCENTILE)
   {
      threshold = priorPercentileThreshold;
      gateValue = MathAbs(vel1);
      gateDirection = (vel1 > 0.0 ? 1 : (vel1 < 0.0 ? -1 : 0));
      if(priorPercentileSamples < MathMax(1, InpSpeedWindowSamples) ||
         threshold <= 0.0 || gateDirection == 0)
         return;
   }

   lastSpeedComputedThreshold = threshold;
   lastSpeedGateValue = gateValue;
   lastSpeedThresholdSamples = (InpSpeedThresholdMode == PERCENTILE
                                ? priorPercentileSamples : 0);

   if(gateValue < threshold)
   {
      if((UsePreSpeedRadar || UsePreSpeedAgainstDefense) && threshold > 0.0 && gateValue > 0.0)
      {
         int watchDir = gateDirection;
         double ratio = gateValue / threshold;
         long cooldownMs = (long)MathMax(1, PreSpeedLogCooldownSeconds) * 1000;
         int signalLevel = 0;

         if(ratio >= PreSpeedStrongRatio)
            signalLevel = 70;
         else if(ratio >= PreSpeedEarlyRatio)
            signalLevel = 50;

         if(signalLevel > 0)
         {
            preSpeedLastSignalMs = t.time_msc;
            preSpeedLastSignalDir = watchDir;
            preSpeedLastSignalLevel = signalLevel;
            preSpeedLastSignalMove = gateValue;
            preSpeedLastSignalRatio = ratio;
            preSpeedLastSignalV1 = vel1;
            preSpeedLastSignalV3 = vel3;
            preSpeedLastSignalV5 = vel5;
         }

         if(UsePreSpeedRadar && signalLevel >= 70)
         {
            if(preSpeedStrongLastDir != watchDir || t.time_msc - preSpeedStrongLastLogMs >= cooldownMs)
            {
               preSpeedStrongLastDir = watchDir;
               preSpeedStrongLastLogMs = t.time_msc;
               LogInfo("PRE_SPEED_70", StringFormat("dir=%d move=%.1f threshold=%.1f ratio=%.2f spread=%.1f v1=%.1f v3=%.1f v5=%.1f",
                       watchDir, gateValue, threshold, ratio, spreadPts, vel1, vel3, vel5));
            }
         }
         else if(UsePreSpeedRadar && signalLevel >= 50)
         {
            if(preSpeedEarlyLastDir != watchDir || t.time_msc - preSpeedEarlyLastLogMs >= cooldownMs)
            {
               preSpeedEarlyLastDir = watchDir;
               preSpeedEarlyLastLogMs = t.time_msc;
               LogInfo("PRE_SPEED_50", StringFormat("dir=%d move=%.1f threshold=%.1f ratio=%.2f spread=%.1f v1=%.1f v3=%.1f v5=%.1f",
                       watchDir, gateValue, threshold, ratio, spreadPts, vel1, vel3, vel5));
            }
         }
      }
      return;
   }

   speedActive = true;
   speedStartMs = tickMs[idx];
   speedStartMid = tickMid[idx];
   speedDir = gateDirection;
   speedPoints = gateValue;
   LogInfo("SPEED_ALERT", StringFormat("dir=%d move=%.1f threshold=%.1f mode=%s threshold_samples=%d spread=%.1f v1=%.1f v3=%.1f v5=%.1f",
           speedDir, speedPoints, threshold,
           (InpSpeedThresholdMode == FIXED ? "FIXED" : "PERCENTILE"),
           lastSpeedThresholdSamples, spreadPts, vel1, vel3, vel5));
   DrawSpeedAlertVisual(t, mid, absMovePts, threshold, spreadPts);
}

//+------------------------------------------------------------------+
datetime SpeedVisualTime(const long ms)
{
   if(ms <= 0)
      return TimeCurrent();
   return (datetime)(ms / 1000);
}

//+------------------------------------------------------------------+
string SpeedVisualName(const int id, const string suffix)
{
   return SpeedVisualPrefix + IntegerToString(id) + "_" + suffix;
}

//+------------------------------------------------------------------+
void SpeedVisualStyleObject(const string name, const color clr, const int width = 1)
{
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
}

//+------------------------------------------------------------------+
void DrawSpeedAlertVisual(const MqlTick &t, const double alertMid, const double impulsePts,
                          const double thresholdPts, const double spreadPts)
{
   if(!ShowSpeedVisuals)
      return;

   int id = ++speedVisualCounter;
   datetime alertTime = SpeedVisualTime(t.time_msc);
   datetime startTime = SpeedVisualTime(speedStartMs);
   color alertColor = (speedDir > 0 ? SpeedVisualBuyColor : SpeedVisualSellColor);
   string dirText = (speedDir > 0 ? "BUY speed" : "SELL speed");
   double offset = MathMax(1.0, SpeedVisualTextOffsetPoints) * _Point;
   double labelPrice = alertMid + (speedDir > 0 ? offset : -offset);

   string marker = SpeedVisualName(id, "MARK");
   if(ObjectCreate(0, marker, OBJ_ARROW, 0, alertTime, alertMid))
   {
      ObjectSetInteger(0, marker, OBJPROP_ARROWCODE, SpeedVisualMarkerCode);
      ObjectSetString(0, marker, OBJPROP_TOOLTIP,
                      dirText + " | move " + DoubleToString(impulsePts, 1) +
                      " pts | threshold " + DoubleToString(thresholdPts, 1) +
                      " | spread " + DoubleToString(spreadPts, 1));
      SpeedVisualStyleObject(marker, alertColor, 1);
   }

   if(SpeedVisualShowAlertText)
   {
      string text = SpeedVisualName(id, "TEXT");
      if(ObjectCreate(0, text, OBJ_TEXT, 0, alertTime, labelPrice))
      {
         ObjectSetString(0, text, OBJPROP_TEXT,
                         dirText + " " + DoubleToString(impulsePts, 1) + " pts");
         ObjectSetInteger(0, text, OBJPROP_FONTSIZE, 7);
         ObjectSetString(0, text, OBJPROP_FONT, "Arial");
         SpeedVisualStyleObject(text, alertColor, 1);
      }
   }

   if(SpeedVisualDrawImpulseLine && speedStartMid > 0.0 && speedStartMs > 0 && startTime != alertTime)
   {
      string impulse = SpeedVisualName(id, "IMPULSE");
      if(ObjectCreate(0, impulse, OBJ_TREND, 0, startTime, speedStartMid, alertTime, alertMid))
      {
         ObjectSetInteger(0, impulse, OBJPROP_RAY_RIGHT, false);
         ObjectSetInteger(0, impulse, OBJPROP_STYLE, STYLE_DOT);
         ObjectSetString(0, impulse, OBJPROP_TOOLTIP,
                         "speed impulse " + DoubleToString(impulsePts, 1) + " pts");
         SpeedVisualStyleObject(impulse, alertColor, 1);
      }
   }

   if(SpeedVisualDrawNextDistance && lastVisualSpeedMs > 0 && lastVisualSpeedPrice > 0.0)
   {
      datetime prevTime = SpeedVisualTime(lastVisualSpeedMs);
      double signedDistancePts = (alertMid - lastVisualSpeedPrice) / _Point;
      double absDistancePts = MathAbs(signedDistancePts);
      string nextLine = SpeedVisualName(id, "NEXT_DIST");
      if(ObjectCreate(0, nextLine, OBJ_TREND, 0, prevTime, lastVisualSpeedPrice, alertTime, alertMid))
      {
         ObjectSetInteger(0, nextLine, OBJPROP_RAY_RIGHT, false);
         ObjectSetInteger(0, nextLine, OBJPROP_STYLE, STYLE_DOT);
         ObjectSetString(0, nextLine, OBJPROP_TOOLTIP,
                         "speed-to-speed " + DoubleToString(absDistancePts, 1) +
                         " pts (" + DoubleToString(signedDistancePts, 1) + ")");
         SpeedVisualStyleObject(nextLine, SpeedVisualDistanceColor, 1);
      }

      if(SpeedVisualShowDistanceText)
      {
         string nextText = SpeedVisualName(id, "NEXT_TEXT");
         datetime midTime = (datetime)(((long)prevTime + (long)alertTime) / 2);
         double midPrice = (lastVisualSpeedPrice + alertMid) * 0.5;
         if(ObjectCreate(0, nextText, OBJ_TEXT, 0, midTime, midPrice))
         {
            ObjectSetString(0, nextText, OBJPROP_TEXT,
                            "S2S " + DoubleToString(absDistancePts, 1));
            ObjectSetInteger(0, nextText, OBJPROP_FONTSIZE, 7);
            ObjectSetString(0, nextText, OBJPROP_FONT, "Arial");
            SpeedVisualStyleObject(nextText, SpeedVisualDistanceColor, 1);
         }
      }
   }

   lastVisualSpeedMs = t.time_msc;
   lastVisualSpeedPrice = alertMid;
   SpeedVisualPrune();
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
void SpeedVisualDeleteId(const int id)
{
   ObjectDelete(0, SpeedVisualName(id, "MARK"));
   ObjectDelete(0, SpeedVisualName(id, "TEXT"));
   ObjectDelete(0, SpeedVisualName(id, "IMPULSE"));
   ObjectDelete(0, SpeedVisualName(id, "NEXT_DIST"));
   ObjectDelete(0, SpeedVisualName(id, "NEXT_TEXT"));
}

//+------------------------------------------------------------------+
void SpeedVisualPrune()
{
   if(SpeedVisualKeepAlerts <= 0)
      return;
   int oldId = speedVisualCounter - SpeedVisualKeepAlerts;
   if(oldId > 0)
      SpeedVisualDeleteId(oldId);
}

//+------------------------------------------------------------------+
void SpeedVisualDeleteAll()
{
   int total = ObjectsTotal(0, 0, -1);
   for(int i = total - 1; i >= 0; i--)
   {
      string name = ObjectName(0, i, 0, -1);
      if(StringFind(name, SpeedVisualPrefix) == 0)
         ObjectDelete(0, name);
   }
}

//+------------------------------------------------------------------+
void BuildDirectionState(const MqlTick &t, DirectionState &s)
{
   ResetState(s);
   s.capture.quote_bid=t.bid;s.capture.quote_ask=t.ask;s.capture.quote_time_msc=t.time_msc;
   double spreadPts = (t.ask - t.bid) / _Point;

   s.spreadStable = (spreadPts <= MaxSpreadPoints);
   if(s.spreadStable)
   {
      s.buyScore += SpreadStableScore;
      s.sellScore += SpreadStableScore;
   }

   if(speedDir > 0)
      s.buyScore += SpeedDirectionScore;
   else if(speedDir < 0)
      s.sellScore += SpeedDirectionScore;

   ScoreCandle(t, s);
   ScoreMicroBreak(t, s);
   ScoreOrderFlow(s);
   SARCaptureMasterVwap(s.capture,s.capturedMasterVwap,(t.bid+t.ask)*0.5);
   ScoreFollowAndMfeMae(t, s);

   int winner = WinnerSide(s);
   s.flowAgreesWithWinner = (winner != 0 && s.flowDir == winner);
   s.flowDisagreesWithWinner = (winner != 0 && s.flowDir == -winner);
   s.oppositePressure = DetectOppositePressure(winner, t.time_msc);
   s.snapback = DetectSpeedSnapback(t);
   bool speedWithWinner = (winner != 0 && speedDir == winner);
   bool followWithWinner = (speedWithWinner && (s.follow21 || s.follow37));
   bool mfeMaeWithWinner = (speedWithWinner && s.mfe > MathAbs(s.mae));

   s.continuation = (winner != 0 && s.spreadStable &&
                     (followWithWinner || mfeMaeWithWinner) &&
                     !s.oppositePressure &&
                     (s.bodyDir == winner || s.microDir == winner));

   s.exhaustion = ((s.upperWickPts > MathMax(20.0, s.bodyPts * 1.25) && speedDir > 0) ||
                   (s.lowerWickPts > MathMax(20.0, s.bodyPts * 1.25) && speedDir < 0) ||
                   s.snapback ||
                   s.oppositePressure ||
                   !s.spreadStable);

   BuildScenarioAndLabels(s);
}

//+------------------------------------------------------------------+
void ResetState(DirectionState &s)
{
   SARCaptureReset(s.capture);
   ResetMasterVwapTelemetry(s.capturedMasterVwap,0.0);
   s.buyScore = 0.0;
   s.sellScore = 0.0;
   s.spreadStable = false;
   s.bodyDir = 0;
   s.microDir = 0;
   s.flowDir = 0;
   s.flowFresh = false;
   s.flowAgreesWithWinner = false;
   s.flowDisagreesWithWinner = false;
   s.follow21 = false;
   s.follow37 = false;
   s.oppositePressure = false;
   s.snapback = false;
   s.continuation = false;
   s.exhaustion = false;
   s.retestHeld = false;
   s.retestFailed = false;
   s.bodyPts = 0.0;
   s.upperWickPts = 0.0;
   s.lowerWickPts = 0.0;
   s.forceImb = 0.0;
   s.nearImb = 0.0;
   s.bookImb = 0.0;
   s.mfe = 0.0;
   s.mae = 0.0;
   s.scenario = "MIXED";
   s.labels = "SPEED_ALERT";
}

//+------------------------------------------------------------------+
void ScoreCandle(const MqlTick &t, DirectionState &s)
{
   double open = iOpen(_Symbol, PERIOD_CURRENT, CandleIndexToCheck);
   double high = iHigh(_Symbol, PERIOD_CURRENT, CandleIndexToCheck);
   double low = iLow(_Symbol, PERIOD_CURRENT, CandleIndexToCheck);
   double close = (CandleIndexToCheck == 0 ? (t.bid + t.ask) * 0.5 : iClose(_Symbol, PERIOD_CURRENT, CandleIndexToCheck));
   if(open <= 0.0 || high <= 0.0 || low <= 0.0)
      return;

   double bodySigned = (close - open) / _Point;
   s.bodyPts = MathAbs(bodySigned);
   s.upperWickPts = (high - MathMax(open, close)) / _Point;
   s.lowerWickPts = (MathMin(open, close) - low) / _Point;

   if(s.bodyPts < MinCandleBodyPoints)
      return;

   if(bodySigned > 0.0)
   {
      s.bodyDir = 1;
      s.buyScore += CandleBodyScore;
   }
   else if(bodySigned < 0.0)
   {
      s.bodyDir = -1;
      s.sellScore += CandleBodyScore;
   }
}

//+------------------------------------------------------------------+
void ScoreMicroBreak(const MqlTick &t, DirectionState &s)
{
   int idx = FirstTickAtOrAfter(t.time_msc - MicroBreakLookbackSeconds * 1000);
   if(idx < 0)
      return;

   int n = ArraySize(tickMid);
   int last = n - 2;
   if(last < idx)
      return;
   double hi = tickMid[idx];
   double lo = tickMid[idx];
   for(int i = idx; i <= last; i++)
   {
      hi = MathMax(hi, tickMid[i]);
      lo = MathMin(lo, tickMid[i]);
   }

   double mid = (t.bid + t.ask) * 0.5;
   double buf = MicroBreakBufferPoints * _Point;
   if(mid > hi + buf)
   {
      s.microDir = 1;
      s.buyScore += MicroBreakScore;
   }
   if(mid < lo - buf)
   {
      s.microDir = -1;
      s.sellScore += MicroBreakScore;
   }
}

//+------------------------------------------------------------------+
void ScoreOrderFlow(DirectionState &s)
{
   if(!UseOrderFlow || StringLen(FlowGVPrefix) <= 0)
   { s.capture.first_blocker="NOT_APPLIED";return; }

   string p = FlowGVPrefix;
   if(!SARCaptureCheck(p + "OK",s.capture.ok) || !SARCaptureCheck(p + "HEARTBEAT",s.capture.heartbeat))
   { s.capture.first_blocker=(!s.capture.ok.exists ? "OK_MISSING" : "HEARTBEAT_MISSING");return; }
   if(SARCaptureGet(p + "OK",s.capture.ok) < 0.5)
   { s.capture.first_blocker=(s.capture.ok.read_ok ? "OK_BELOW_HALF" : "OK_READ_FAILED");return; }

   s.capture.consume_uptime_ms=GetTickCount64();
   double age = (double)s.capture.consume_uptime_ms - SARCaptureGet(p + "HEARTBEAT",s.capture.heartbeat);
   s.capture.shared_age_ms=age;s.capture.shared_age_available=s.capture.heartbeat.read_ok;
   if(age > MaxFlowAgeMs)
   { s.capture.first_blocker="HEARTBEAT_STALE";return; }

   s.flowFresh = true;
   s.forceImb = SARCaptureGV(p + "FORCE_IMB",s.capture.force);
   s.nearImb = SARCaptureGV(p + "NEAR_IMB",s.capture.near);
   s.bookImb = SARCaptureGV(p + "BOOK_IMB",s.capture.book);
   s.capture.flow_fresh=s.flowFresh;
   // This verdict describes the existing flow-scoring branch, never overall entry permission.
   // Missing components still contribute the original zero fallback; availability is separate.
   s.capture.first_blocker="RELEASED";

   int buyVotes = 0;
   int sellVotes = 0;
   AddFlowVote(s.forceImb, buyVotes, sellVotes, s);
   AddFlowVote(s.nearImb, buyVotes, sellVotes, s);
   AddFlowVote(s.bookImb, buyVotes, sellVotes, s);

   if(buyVotes >= 2)
      s.flowDir = 1;
   else if(sellVotes >= 2)
      s.flowDir = -1;
}

//+------------------------------------------------------------------+
double GV(const string name)
{
   return (GlobalVariableCheck(name) ? GlobalVariableGet(name) : 0.0);
}

//+------------------------------------------------------------------+
void ResetMasterVwapTelemetry(MasterVwapTelemetry &telemetry,
                              const double brokerMid)
{
   telemetry.valid = false;
   telemetry.degraded = true;
   telemetry.heartbeatAvailable = false;
   telemetry.ageMs = 0;
   telemetry.value = 0.0;
   telemetry.contributors = 0;
   telemetry.brokerMid = brokerMid;
}

//+------------------------------------------------------------------+
void SARCaptureMasterVwap(const SARCaptureLatch &flow,MasterVwapTelemetry &telemetry,const double brokerMid)
{
   ResetMasterVwapTelemetry(telemetry,brokerMid);
   if(!flow.ok.consumed || !flow.ok.read_ok || !flow.heartbeat.consumed || !flow.heartbeat.read_ok) return;
   telemetry.heartbeatAvailable=true;telemetry.ageMs=(long)flow.shared_age_ms;
   if(flow.ok.value<0.5 || telemetry.ageMs<0 || telemetry.ageMs>MaxFlowAgeMs) return;
   string p=FlowGVPrefix;
   if(!GlobalVariableCheck(p+"VWAP_VALID") || GlobalVariableGet(p+"VWAP_VALID")<0.5) return;
   if(!GlobalVariableCheck(p+"VWAP_PRICE") || !GlobalVariableCheck(p+"LIVE_FEEDS")) return;
   double vwap=GlobalVariableGet(p+"VWAP_PRICE");double contributors=GlobalVariableGet(p+"LIVE_FEEDS");
   if(!MathIsValidNumber(vwap) || vwap<=0.0 || !MathIsValidNumber(contributors) || contributors<=0.0) return;
   telemetry.valid=true;telemetry.degraded=false;telemetry.value=vwap;telemetry.contributors=(int)MathRound(contributors);
}

void ReadMasterVwapTelemetry(const double brokerMid,
                             MasterVwapTelemetry &telemetry)
{
   ResetMasterVwapTelemetry(telemetry, brokerMid);

   if(StringLen(FlowGVPrefix) <= 0)
      return;

   string p = FlowGVPrefix;
   if(!GlobalVariableCheck(p + "OK") ||
      !GlobalVariableCheck(p + "HEARTBEAT"))
      return;

   double heartbeat = GlobalVariableGet(p + "HEARTBEAT");
   telemetry.heartbeatAvailable = true;
   telemetry.ageMs = (long)((double)GetTickCount64() - heartbeat);

   if(GlobalVariableGet(p + "OK") < 0.5)
      return;
   if(telemetry.ageMs < 0 || telemetry.ageMs > MaxFlowAgeMs)
      return;
   if(!GlobalVariableCheck(p + "VWAP_VALID") ||
      GlobalVariableGet(p + "VWAP_VALID") < 0.5)
      return;
   if(!GlobalVariableCheck(p + "VWAP_PRICE") ||
      !GlobalVariableCheck(p + "LIVE_FEEDS"))
      return;

   double vwap = GlobalVariableGet(p + "VWAP_PRICE");
   double contributors = GlobalVariableGet(p + "LIVE_FEEDS");
   if(!MathIsValidNumber(vwap) || vwap <= 0.0 ||
      !MathIsValidNumber(contributors) || contributors <= 0.0)
      return;

   telemetry.valid = true;
   telemetry.degraded = false;
   telemetry.value = vwap;
   telemetry.contributors = (int)MathRound(contributors);
}

//+------------------------------------------------------------------+
void AddFlowVote(const double v, int &buyVotes, int &sellVotes, DirectionState &s)
{
   if(MathAbs(v) < MinFlowImbalance)
      return;
   if(v > 0.0)
   {
      buyVotes++;
      s.buyScore += FlowComponentScore;
   }
   else
   {
      sellVotes++;
      s.sellScore += FlowComponentScore;
   }
}

//+------------------------------------------------------------------+
void ScoreFollowAndMfeMae(const MqlTick &t, DirectionState &s)
{
   if(!speedActive)
      return;

   int idx = FirstTickAtOrAfter(speedStartMs);
   if(idx < 0)
      return;

   int n = ArraySize(tickMid);
   double mfe = -ROUTER_BIG_VALUE;
   double mae = ROUTER_BIG_VALUE;
   for(int i = idx; i < n; i++)
   {
      double fav = (speedDir > 0 ? (tickMid[i] - speedStartMid) : (speedStartMid - tickMid[i])) / _Point;
      mfe = MathMax(mfe, fav);
      mae = MathMin(mae, fav);
   }
   if(mfe > -ROUTER_BIG_VALUE) s.mfe = mfe;
   if(mae < ROUTER_BIG_VALUE)  s.mae = mae;

   double mid = (t.bid + t.ask) * 0.5;
   double movePts = (speedDir > 0 ? (mid - speedStartMid) : (speedStartMid - mid)) / _Point;
   long elapsed = t.time_msc - speedStartMs;
   s.follow21 = (movePts >= MarketFollow21Points && elapsed <= MarketFollow21Seconds * 1000);
   s.follow37 = (movePts >= MarketFollow37Points && elapsed <= MarketFollow37Seconds * 1000);
}

//+------------------------------------------------------------------+
bool DetectOppositePressure(const int side, const long nowMs)
{
   if(side == 0)
      return false;

   int idx = FirstTickAtOrAfter(nowMs - OppositePressureSeconds * 1000);
   if(idx < 0)
      return false;

   int n = ArraySize(tickMid);
   double ref = tickMid[idx];
   double worst = 0.0;
   for(int i = idx; i < n; i++)
   {
      double moveAgainst = (side > 0 ? (ref - tickMid[i]) : (tickMid[i] - ref)) / _Point;
      worst = MathMax(worst, moveAgainst);
   }
   return (worst >= OppositePressurePoints);
}

//+------------------------------------------------------------------+
bool DetectSpeedSnapback(const MqlTick &t)
{
   if(!speedActive || speedDir == 0 || speedStartMid <= 0.0)
      return false;

   double mid = (t.bid + t.ask) * 0.5;
   double snapPts = 0.0;
   if(speedDir > 0)
      snapPts = (speedStartMid - mid) / _Point;
   else
      snapPts = (mid - speedStartMid) / _Point;

   return (snapPts >= RetestFailPoints);
}

//+------------------------------------------------------------------+
int WinnerSide(const DirectionState &s)
{
   if(s.buyScore >= MinDirectionScore && (s.buyScore - s.sellScore) >= MinScoreEdge)
      return 1;
   if(s.sellScore >= MinDirectionScore && (s.sellScore - s.buyScore) >= MinScoreEdge)
      return -1;
   return 0;
}

//+------------------------------------------------------------------+
void BuildScenarioAndLabels(DirectionState &s)
{
   s.labels = "SPEED_ALERT";
   int winner = WinnerSide(s);
   bool bodyWithTrade = (s.bodyDir != 0 && winner == s.bodyDir);
   bool microWithTrade = (s.microDir != 0 && winner == s.microDir);
   bool speedWithWinner = (winner != 0 && speedDir == winner);
   bool hasFollow = (speedWithWinner && (s.follow21 || s.follow37));
   bool noOpposite = !s.oppositePressure;
   bool goodMfeMae = (speedWithWinner && s.mfe > MathAbs(s.mae));

   if(s.exhaustion)
   {
      s.scenario = "EXHAUSTION_CONFIRMED";
      s.labels += ";EXHAUSTION_CONFIRMED";
   }
   else if(s.continuation)
   {
      s.scenario = "CONTINUATION_CONFIRMED";
      s.labels += ";CONTINUATION_CONFIRMED";
   }
   else if(bodyWithTrade)
      s.scenario = "BODY_WITH_TRADE_ONLY";
   else if(s.bodyDir != 0)
      s.scenario = "BODY_NOT_WITH_TRADE";
   else
      s.scenario = "MIXED";

   if(bodyWithTrade)
      s.labels += ";BODY_WITH_TRADE";
   else if(s.bodyDir != 0 && winner != 0 && s.bodyDir == -winner)
      s.labels += ";BODY_AGAINST_TRADE";
   if(microWithTrade)
      s.labels += ";MICRO_BREAK_WITH_TRADE";
   if(s.follow21)
      s.labels += ";FOLLOW_21";
   if(s.follow37)
      s.labels += ";FOLLOW_37";
   if(!s.spreadStable)
      s.labels += ";SPREAD_TRAP";
   if(s.snapback)
      s.labels += ";SNAPBACK";
   if(speedWithWinner)
      s.labels += ";SPEED_WITH_WINNER";
   else if(winner != 0 && speedDir == -winner)
      s.labels += ";SPEED_AGAINST_WINNER";

   if(bodyWithTrade && hasFollow && s.spreadStable)
      s.labels += ";BODY_FOLLOW_NO_TRAP";
   if(bodyWithTrade && s.spreadStable && (goodMfeMae || hasFollow))
      s.labels += ";QUALITY_ROUTER";
   if(s.continuation)
      s.labels += ";CONTINUATION_EXPANSION";

   if(s.flowDir != 0)
   {
      if(s.flowAgreesWithWinner)
         s.labels += ";FLOW_AGREES";
      else if(s.flowDisagreesWithWinner)
         s.labels += ";FLOW_DISAGREES";
   }

   if(s.oppositePressure)
      s.labels += ";OPPOSITE_PRESSURE";
   else
      s.labels += ";NO_OPPOSITE_PRESSURE";

   if(bodyWithTrade && s.flowAgreesWithWinner)
      s.labels += ";BODY_FLOW_AGREES";
   if(bodyWithTrade && noOpposite)
      s.labels += ";BODY_NO_OPPOSITE";
   if(bodyWithTrade && s.flowAgreesWithWinner && noOpposite)
      s.labels += ";BODY_FLOW_NO_OPPOSITE";
   if(bodyWithTrade && s.flowAgreesWithWinner && noOpposite && hasFollow)
      s.labels += ";BODY_FLOW_NO_OPP_FOLLOW";
   if(bodyWithTrade && s.spreadStable && noOpposite && (hasFollow || goodMfeMae || s.flowAgreesWithWinner))
      s.labels += ";FLEXIBLE_QUALITY_ROUTER";

   if(s.exhaustion)
   {
      if((s.upperWickPts > MathMax(20.0, s.bodyPts * 1.25) && speedDir > 0) ||
         (s.lowerWickPts > MathMax(20.0, s.bodyPts * 1.25) && speedDir < 0))
         s.labels += ";EXH_WICK_REJECTION";
      if(s.snapback)
         s.labels += ";EXH_SNAPBACK";
      if(s.oppositePressure)
         s.labels += ";EXH_OPPOSITE_PRESSURE";
      if(!s.spreadStable)
         s.labels += ";EXH_SPREAD_TRAP";
   }
}

//+------------------------------------------------------------------+
RouterAction DecideAction(const DirectionState &s)
{
   int side = WinnerSide(s);
   if(!s.spreadStable)
      return ActSkip;

   if(BlockStrongFlowAgainst && s.flowDisagreesWithWinner)
      return ActSkip;

   if(s.exhaustion && EntryRouterMode >= StopMarketLimit)
   {
      if(speedDir > 0)
         return ActSellLimit;
      if(speedDir < 0)
         return ActBuyLimit;
   }

   if(side == 0)
      return ActSkip;

   if(speedDir == side && (s.follow21 || s.follow37) &&
      EntryRouterMode >= StopAndMarket && MarketEntryAllowedByFlow(side, s))
      return (side > 0 ? ActBuyMarket : ActSellMarket);

   return (side > 0 ? ActBuyStop : ActSellStop);
}

//+------------------------------------------------------------------+
bool MarketEntryAllowedByFlow(const int side, const DirectionState &s)
{
   bool neutralFlow = (!s.flowFresh || s.flowDir == 0);
   bool weakFlow = (neutralFlow || s.flowDisagreesWithWinner);

   if(side < 0 && DowngradeNeutralSellMarketToStop && neutralFlow)
      return false;

   if(WeakFlowMarketNeedsBodyAndMicro && weakFlow)
   {
      double score = (side > 0 ? s.buyScore : s.sellScore);
      double edge = MathAbs(s.buyScore - s.sellScore);
      bool bodyOk = (s.bodyDir == side && s.bodyPts >= MinCandleBodyPoints);
      bool microOk = (s.microDir == side);
      bool scoreOk = (score >= WeakFlowMarketMinScore && edge >= WeakFlowMarketMinScoreEdge);
      return (bodyOk && microOk && scoreOk);
   }

   return true;
}

//+------------------------------------------------------------------+
void AIPreEntryJourneyResetContext(TheoryAIPreEntryJourneyContextV1 &context)
{
   context.valid = false;
   context.decision_ms = 0;
   context.session_bucket = "";
   context.spread_points = 0.0;
   context.velocity_1s_with_trade = 0.0;
   context.velocity_3s_with_trade = 0.0;
   context.velocity_5s_with_trade = 0.0;
   context.velocity_1s_minus_3s_with_trade = 0.0;
   context.velocity_3s_minus_5s_with_trade = 0.0;
   context.force_imbalance_with_trade = 0.0;
   context.near_imbalance_with_trade = 0.0;
   context.book_imbalance_with_trade = 0.0;
   context.body_direction_with_trade = 0;
   context.micro_direction_with_trade = 0;
   context.flow_direction_with_trade = 0;
   context.flow_fresh = false;
   context.opposite_pressure = false;
   context.continuation = false;
   context.exhaustion = false;
   context.retest_held = false;
   context.retest_failed = false;
   context.own_direction_score = 0.0;
   context.opposite_direction_score = 0.0;
   context.direction_score_edge = 0.0;
}

//+------------------------------------------------------------------+
string AIPreEntryJourneySessionBucket(const datetime eventTime)
{
   MqlDateTime parts;
   TimeToStruct(eventTime, parts);
   if(parts.hour >= 0 && parts.hour < 7)
      return "ASIA";
   if(parts.hour >= 7 && parts.hour < 13)
      return "LONDON";
   if(parts.hour >= 13 && parts.hour < 21)
      return "NEW_YORK";
   return "LATE";
}

//+------------------------------------------------------------------+
void AIPreEntryJourneyBuildContext(const RouterAction action,
                                   const DirectionState &state,
                                   const MqlTick &tick,
                                   TheoryAIPreEntryJourneyContextV1 &context)
{
   AIPreEntryJourneyResetContext(context);
   int side = ActionSide(action);
   if(action == ActSkip || side == 0 || tick.time_msc <= 0)
      return;

   double mid = (tick.ask + tick.bid) * 0.5;
   double velocity1s = SignedVelocityPointsPerSecond(mid,
                                                     tick.time_msc,
                                                     1000) * side;
   double velocity3s = SignedVelocityPointsPerSecond(mid,
                                                     tick.time_msc,
                                                     3000) * side;
   double velocity5s = SignedVelocityPointsPerSecond(mid,
                                                     tick.time_msc,
                                                     5000) * side;

   context.valid = true;
   context.decision_ms = tick.time_msc;
   context.session_bucket =
      AIPreEntryJourneySessionBucket((datetime)(tick.time_msc / 1000));
   context.spread_points = (tick.ask - tick.bid) / _Point;
   context.velocity_1s_with_trade = velocity1s;
   context.velocity_3s_with_trade = velocity3s;
   context.velocity_5s_with_trade = velocity5s;
   context.velocity_1s_minus_3s_with_trade = velocity1s - velocity3s;
   context.velocity_3s_minus_5s_with_trade = velocity3s - velocity5s;
   context.force_imbalance_with_trade = state.forceImb * side;
   context.near_imbalance_with_trade = state.nearImb * side;
   context.book_imbalance_with_trade = state.bookImb * side;
   context.body_direction_with_trade = state.bodyDir * side;
   context.micro_direction_with_trade = state.microDir * side;
   context.flow_direction_with_trade = state.flowDir * side;
   context.flow_fresh = state.flowFresh;
   context.opposite_pressure = state.oppositePressure;
   context.continuation = state.continuation;
   context.exhaustion = state.exhaustion;
   context.retest_held = state.retestHeld;
   context.retest_failed = state.retestFailed;
   context.own_direction_score = (side > 0
                                  ? state.buyScore
                                  : state.sellScore);
   context.opposite_direction_score = (side > 0
                                       ? state.sellScore
                                       : state.buyScore);
   context.direction_score_edge =
      context.own_direction_score - context.opposite_direction_score;
}

//+------------------------------------------------------------------+
bool PlaceAction(const RouterAction action, const MqlTick &t, const DirectionState &s)
{
   SARCaptureLatch captureMutable;
   SARCaptureCommit(s.capture,t,captureMutable);
#ifdef SAR_CAPTURE_SMOKE
   captureMutable.position_id="26090568001";
   SARCaptureDecisionGate(captureMutable,"PLUMBING_SIMULATED","COMPILE_TIME_FIXTURE_NO_TRADE_API");
#endif
   const SARCaptureLatch capture=captureMutable;
   DirectionState captureState=s;
   captureState.capture=capture;
#ifdef SAR_CAPTURE_SMOKE
   SARCaptureSmokeCommit(action,t,captureState,capture);
   return false;
#endif
   TheoryAIPreEntryJourneyContextV1 aiJourneyContext;
   AIPreEntryJourneyBuildContext(action, s, t, aiJourneyContext);
   double preEntryScore = 0.0;
   string preEntryBucket = "";
   string preEntryAllow = "";
   string preEntryBlock = "";
   string preEntrySignals = "";
   string v471TapeHealth = "";
   double v471VelocityDecay = 0.0;
   long v471PreSpeedAgeMs = -1;
   string v48Mode2Signal = "";
   string v48Mode2BlockReason = "";
   int v48Mode2OppFlags = 0;
   double v48Mode2Velocity1s = 0.0;
   double v48Mode2WeightFactor = 1.0;
   BuildV45PreEntryHighShadowTelemetry(action, s,
                                       preEntryScore,
                                       preEntryBucket,
                                       preEntryAllow,
                                       preEntryBlock,
                                       preEntrySignals);
   if(UseV471TelemetryRepair && action != ActSkip)
   {
      v471TapeHealth = V471BuildPreEntryTapeHealth(t);
      v471VelocityDecay = V471PreEntryVelocityDecay(t);
      v471PreSpeedAgeMs = V471PreSpeedSignalAgeMs(t.time_msc);
   }
   BuildV48Mode2ShadowScorecard(action,
                                s,
                                t,
                                v48Mode2Signal,
                                v48Mode2BlockReason,
                                v48Mode2OppFlags,
                                v48Mode2Velocity1s,
                                v48Mode2WeightFactor);

   if(!TradingEnabled)
   {
      SARCaptureLatch disabledMutable=capture;
      SARCaptureDecisionGate(disabledMutable,"BLOCKED","TradingEnabled=false");
      const SARCaptureLatch disabledCapture=disabledMutable;
      captureState.capture=disabledCapture;
      LogDecision("SHADOW_" + ActionName(action), action, captureState, "TradingEnabled=false", 0.0, 0.0, 0.0, 0.0);
      AIDecisionAttemptLog(disabledCapture, action,
                           ActionSide(action),
                           aiJourneyContext,
                           preEntryScore,
                           preEntryBucket,
                           preEntryAllow,
                           preEntryBlock,
                           preEntrySignals,
                           v471TapeHealth,
                           v471VelocityDecay,
                           v471PreSpeedAgeMs,
                           v48Mode2Signal,
                           v48Mode2BlockReason,
                           v48Mode2OppFlags,
                           v48Mode2Velocity1s,
                           v48Mode2WeightFactor,
                           0.0, 0.0, 0.0, 0.0,
                           false, false, false, 0, 0,
                           "TRADING_DISABLED");
      return false;
   }

   double lots = NormalizeLots(FixedLot * LotFactorForAction(action, s));
   double entry = 0.0, sl = 0.0, tp = 0.0;
   string continuationIntent="";
   string comment = ShortComment(action, s);
   int actionSide = ActionSide(action);
   bool ok = false;

   // Immutable candidate receipts exist before any API; only the reached branch selects one.
   SARCaptureLatch releasedMutable=capture,lotBlockedMutable=capture;
   SARCaptureDecisionGate(releasedMutable,"RELEASED","RELEASED");
   SARCaptureDecisionGate(lotBlockedMutable,"BLOCKED","lots<=0");
   const SARCaptureLatch releasedCapture=releasedMutable;
   const SARCaptureLatch lotBlockedCapture=lotBlockedMutable;
   bool captureTradeApiAttempted=false;

   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(SlippagePoints);

   if(action == ActBuyMarket)
   {
      entry = t.ask;
      BuildSlTp(1, entry, MarketSLPoints, MarketTPPoints, "BUY_MARKET_INITIAL_SL", sl, tp);
      if(InpUseTrueStopRiskSizing)
         lots = CalibratedLots(1, entry, sl, lots);
      if(lots <= 0.0)
      {
         captureState.capture=lotBlockedCapture;
         LogDecision("SKIP_" + ActionName(action),action,captureState,"lots<=0",lots,entry,sl,tp);
         return false;
      }
       if(InpUseContinuationFreeze)
       {
          if(!CFRPrepareOrder(comment,actionSide,entry,tp,sl,lots,t.time_msc,continuationIntent))
             return false;
          tp=0.0; // Actual broker request; original TP is persisted in the intent.
       }
       captureTradeApiAttempted=true;
      ok = trade.Buy(lots, _Symbol, 0.0, sl, tp, comment);
   }
   else if(action == ActSellMarket)
   {
      entry = t.bid;
      BuildSlTp(-1, entry, MarketSLPoints, MarketTPPoints, "SELL_MARKET_INITIAL_SL", sl, tp);
      if(InpUseTrueStopRiskSizing)
         lots = CalibratedLots(-1, entry, sl, lots);
      if(lots <= 0.0)
      {
         captureState.capture=lotBlockedCapture;
         LogDecision("SKIP_" + ActionName(action),action,captureState,"lots<=0",lots,entry,sl,tp);
         return false;
      }
       if(InpUseContinuationFreeze)
       {
          if(!CFRPrepareOrder(comment,actionSide,entry,tp,sl,lots,t.time_msc,continuationIntent))
             return false;
          tp=0.0; // Actual broker request; original TP is persisted in the intent.
       }
       captureTradeApiAttempted=true;
      ok = trade.Sell(lots, _Symbol, 0.0, sl, tp, comment);
   }
   else if(action == ActBuyStop)
   {
      entry = LegalPrice(ORDER_TYPE_BUY_STOP, t, t.ask + StopEntryDistancePoints * _Point);
      BuildSlTp(1, entry, StopSLPoints, StopTPPoints, "BUY_STOP_INITIAL_SL", sl, tp);
      if(InpUseTrueStopRiskSizing)
         lots = CalibratedLots(1, entry, sl, lots);
      if(lots <= 0.0)
      {
         captureState.capture=lotBlockedCapture;
         LogDecision("SKIP_" + ActionName(action),action,captureState,"lots<=0",lots,entry,sl,tp);
         return false;
      }
       if(InpUseContinuationFreeze)
       {
          if(!CFRPrepareOrder(comment,actionSide,entry,tp,sl,lots,t.time_msc,continuationIntent))
             return false;
          tp=0.0; // Actual broker request; original TP is persisted in the intent.
       }
       captureTradeApiAttempted=true;
      ok = trade.BuyStop(lots, entry, _Symbol, sl, tp, ORDER_TIME_GTC, 0, comment);
   }
   else if(action == ActSellStop)
   {
      entry = LegalPrice(ORDER_TYPE_SELL_STOP, t, t.bid - StopEntryDistancePoints * _Point);
      BuildSlTp(-1, entry, StopSLPoints, StopTPPoints, "SELL_STOP_INITIAL_SL", sl, tp);
      if(InpUseTrueStopRiskSizing)
         lots = CalibratedLots(-1, entry, sl, lots);
      if(lots <= 0.0)
      {
         captureState.capture=lotBlockedCapture;
         LogDecision("SKIP_" + ActionName(action),action,captureState,"lots<=0",lots,entry,sl,tp);
         return false;
      }
       if(InpUseContinuationFreeze)
       {
          if(!CFRPrepareOrder(comment,actionSide,entry,tp,sl,lots,t.time_msc,continuationIntent))
             return false;
          tp=0.0; // Actual broker request; original TP is persisted in the intent.
       }
       captureTradeApiAttempted=true;
      ok = trade.SellStop(lots, entry, _Symbol, sl, tp, ORDER_TIME_GTC, 0, comment);
   }
   else if(action == ActBuyLimit)
   {
      entry = LegalPrice(ORDER_TYPE_BUY_LIMIT, t, t.bid - LimitRetestDistancePoints * _Point);
      BuildSlTp(1, entry, LimitSLPoints, LimitTPPoints, "BUY_LIMIT_INITIAL_SL", sl, tp);
      if(InpUseTrueStopRiskSizing)
         lots = CalibratedLots(1, entry, sl, lots);
      if(lots <= 0.0)
      {
         captureState.capture=lotBlockedCapture;
         LogDecision("SKIP_" + ActionName(action),action,captureState,"lots<=0",lots,entry,sl,tp);
         return false;
      }
       if(InpUseContinuationFreeze)
       {
          if(!CFRPrepareOrder(comment,actionSide,entry,tp,sl,lots,t.time_msc,continuationIntent))
             return false;
          tp=0.0; // Actual broker request; original TP is persisted in the intent.
       }
       captureTradeApiAttempted=true;
      ok = trade.BuyLimit(lots, entry, _Symbol, sl, tp, ORDER_TIME_GTC, 0, comment);
   }
   else if(action == ActSellLimit)
   {
      entry = LegalPrice(ORDER_TYPE_SELL_LIMIT, t, t.ask + LimitRetestDistancePoints * _Point);
      BuildSlTp(-1, entry, LimitSLPoints, LimitTPPoints, "SELL_LIMIT_INITIAL_SL", sl, tp);
      if(InpUseTrueStopRiskSizing)
         lots = CalibratedLots(-1, entry, sl, lots);
      if(lots <= 0.0)
      {
         captureState.capture=lotBlockedCapture;
         LogDecision("SKIP_" + ActionName(action),action,captureState,"lots<=0",lots,entry,sl,tp);
         return false;
      }
       if(InpUseContinuationFreeze)
       {
          if(!CFRPrepareOrder(comment,actionSide,entry,tp,sl,lots,t.time_msc,continuationIntent))
             return false;
          tp=0.0; // Actual broker request; original TP is persisted in the intent.
       }
       captureTradeApiAttempted=true;
      ok = trade.SellLimit(lots, entry, _Symbol, sl, tp, ORDER_TIME_GTC, 0, comment);
   }

   CFRFinishOrder(continuationIntent,ok);
   SARCaptureLatch resultMutable=capture;
   if(captureTradeApiAttempted) resultMutable=releasedCapture;
   const SARCaptureLatch resultCapture=resultMutable;
   captureState.capture=resultCapture;

   if(ok)
   {
      uint retcode = trade.ResultRetcode();
      double executed = (IsPendingAction(action) ? 0.0 : trade.ResultPrice());
      CaptureTradeMeasurement(entry, executed, actionSide, false, t, retcode);
      ulong requestTicket = trade.ResultOrder();
      if(requestTicket == 0)
         requestTicket = trade.ResultDeal();
      PendingRequestAdd(requestTicket, action, entry, t.time_msc,
                        preEntryScore,
                        preEntryBucket,
                        preEntryAllow,
                        preEntryBlock,
                        preEntrySignals,
                        v471TapeHealth,
                        v471VelocityDecay,
                        v471PreSpeedAgeMs,
                        v48Mode2Signal,
                        v48Mode2BlockReason,
                        v48Mode2OppFlags,
                        v48Mode2Velocity1s,
                        v48Mode2WeightFactor,
                        aiJourneyContext);
      LogDecision("PLACED_" + ActionName(action), action, captureState,
                  "ok request_ticket=" + (string)requestTicket +
                  " decision_ms=" + (string)t.time_msc,
                  lots, entry, sl, tp);
      AIDecisionAttemptLog(resultCapture, action,
                           actionSide,
                           aiJourneyContext,
                           preEntryScore,
                           preEntryBucket,
                           preEntryAllow,
                           preEntryBlock,
                           preEntrySignals,
                           v471TapeHealth,
                           v471VelocityDecay,
                           v471PreSpeedAgeMs,
                           v48Mode2Signal,
                           v48Mode2BlockReason,
                           v48Mode2OppFlags,
                           v48Mode2Velocity1s,
                           v48Mode2WeightFactor,
                           lots, entry, sl, tp,
                           true, true, true,
                           requestTicket, retcode,
                           trade.ResultRetcodeDescription());
      return true;
   }

   uint failedRetcode = trade.ResultRetcode();
   string failedDescription = trade.ResultRetcodeDescription();
   CaptureTradeMeasurement(entry, 0.0, actionSide, false, t, failedRetcode);
   LogDecision("FAILED_" + ActionName(action), action, captureState,
               StringFormat("%u %s", failedRetcode, failedDescription),
               lots, entry, sl, tp);
   AIDecisionAttemptLog(resultCapture, action,
                        actionSide,
                        aiJourneyContext,
                        preEntryScore,
                        preEntryBucket,
                        preEntryAllow,
                        preEntryBlock,
                        preEntrySignals,
                        v471TapeHealth,
                        v471VelocityDecay,
                        v471PreSpeedAgeMs,
                        v48Mode2Signal,
                        v48Mode2BlockReason,
                        v48Mode2OppFlags,
                        v48Mode2Velocity1s,
                        v48Mode2WeightFactor,
                        lots, entry, sl, tp,
                        true, true, false,
                        0, failedRetcode, failedDescription);
   return false;
}

//+------------------------------------------------------------------+
double LotFactorForAction(const RouterAction action, const DirectionState &s)
{
   if(action == ActBuyMarket || action == ActSellMarket)
      return MathMax(0.0, FollowThroughMarketLotFactor);
   if(action == ActBuyLimit || action == ActSellLimit)
      return MathMax(0.0, ExhaustionLimitLotFactor);
   if(s.continuation)
      return MathMax(0.0, ContinuationStopLotFactor);
   if(s.scenario == "BODY_WITH_TRADE_ONLY")
      return MathMax(0.0, BodyOnlyLotFactor);
   return 1.0;
}

//+------------------------------------------------------------------+
string ShortComment(const RouterAction action, const DirectionState &s)
{
   string c = "SAR:" + ScenarioKeyForAction(action, s) + ":" + ActionShortName(action);
   if(s.flowAgreesWithWinner) c += ":FA";
   else if(s.flowDisagreesWithWinner) c += ":FD";
   if(s.oppositePressure) c += ":OP";
   return StringSubstr(c, 0, 31);
}

//+------------------------------------------------------------------+
string ActionShortName(const RouterAction action)
{
   if(action == ActBuyStop) return "BS";
   if(action == ActSellStop) return "SS";
   if(action == ActBuyMarket) return "BM";
   if(action == ActSellMarket) return "SM";
   if(action == ActBuyLimit) return "BL";
   if(action == ActSellLimit) return "SL";
   return "SK";
}

//+------------------------------------------------------------------+
string ScenarioKeyForAction(const RouterAction action, const DirectionState &s)
{
   if(action == ActBuyMarket || action == ActSellMarket)
      return "FOLM";
   if(action == ActBuyLimit || action == ActSellLimit)
      return "EXHL";
   if(StringFind(s.labels, "BODY_FLOW_NO_OPP_FOLLOW") >= 0)
      return "BFNF";
   if(StringFind(s.labels, "FLEXIBLE_QUALITY_ROUTER") >= 0)
      return "FLXQ";
   if(StringFind(s.labels, "QUALITY_ROUTER") >= 0)
      return "QUAL";
   if(StringFind(s.labels, "BODY_FOLLOW_NO_TRAP") >= 0)
      return "BFOL";
   if(StringFind(s.labels, "BODY_FLOW_NO_OPPOSITE") >= 0)
      return "BFNO";
   if(StringFind(s.labels, "BODY_NO_OPPOSITE") >= 0)
      return "BNO";
   if(StringFind(s.labels, "BODY_FLOW_AGREES") >= 0)
      return "BFA";
   if(s.scenario == "BODY_WITH_TRADE_ONLY")
      return "BODY";
   if(s.continuation)
      return "CONT";
   if(s.exhaustion)
      return "EXH";
   return "OTHER";
}

//+------------------------------------------------------------------+
string ActionName(const RouterAction action)
{
   if(action == ActBuyStop) return "BUY_STOP";
   if(action == ActSellStop) return "SELL_STOP";
   if(action == ActBuyMarket) return "BUY_MKT";
   if(action == ActSellMarket) return "SELL_MKT";
   if(action == ActBuyLimit) return "BUY_LIMIT";
   if(action == ActSellLimit) return "SELL_LIMIT";
   return "SKIP";
}

//+------------------------------------------------------------------+
bool StringEndsWith(const string value, const string suffix)
{
   int valueLen = StringLen(value);
   int suffixLen = StringLen(suffix);
   return (suffixLen <= valueLen && StringSubstr(value, valueLen - suffixLen) == suffix);
}

//+------------------------------------------------------------------+
RouterAction ActionFromLabels(const string labels)
{
   if(StringFind(labels, ":BS:") >= 0 || StringEndsWith(labels, ":BS")) return ActBuyStop;
   if(StringFind(labels, ":SS:") >= 0 || StringEndsWith(labels, ":SS")) return ActSellStop;
   if(StringFind(labels, ":BM:") >= 0 || StringEndsWith(labels, ":BM")) return ActBuyMarket;
   if(StringFind(labels, ":SM:") >= 0 || StringEndsWith(labels, ":SM")) return ActSellMarket;
   if(StringFind(labels, ":BL:") >= 0 || StringEndsWith(labels, ":BL")) return ActBuyLimit;
   if(StringFind(labels, ":SL:") >= 0 || StringEndsWith(labels, ":SL")) return ActSellLimit;
   return ActSkip;
}

//+------------------------------------------------------------------+
string ActionDestination(const RouterAction action)
{
   if(action == ActBuyStop || action == ActBuyMarket || action == ActBuyLimit)
      return "BUY";
   if(action == ActSellStop || action == ActSellMarket || action == ActSellLimit)
      return "SELL";
   return "NONE";
}

//+------------------------------------------------------------------+
int ActionSide(const RouterAction action)
{
   if(action == ActBuyStop || action == ActBuyMarket || action == ActBuyLimit)
      return 1;
   if(action == ActSellStop || action == ActSellMarket || action == ActSellLimit)
      return -1;
   return 0;
}

//+------------------------------------------------------------------+
bool IsPendingAction(const RouterAction action)
{
   return (action == ActBuyStop || action == ActSellStop ||
           action == ActBuyLimit || action == ActSellLimit);
}

//+------------------------------------------------------------------+
string MeasurementDouble(const bool active, const double value, const int digits)
{
   if(!active)
      return "";
   return DoubleToString(value, digits);
}

//+------------------------------------------------------------------+
string MeasurementDoubleSentinel(const bool active, const double value, const int digits)
{
   if(!active || value > ROUTER_BIG_VALUE * 0.5)
      return "";
   return DoubleToString(value, digits);
}

//+------------------------------------------------------------------+
string MeasurementLong(const bool active, const long value)
{
   if(!active || value <= 0)
      return "";
   return (string)value;
}

//+------------------------------------------------------------------+
bool ValidTelemetrySnapshot(const double value)
{
   return (value < ROUTER_BIG_VALUE * 0.5);
}

//+------------------------------------------------------------------+
double NormalizeRange01(const double value, const double low, const double high)
{
   if(high <= low)
      return 0.0;
   double v = (value - low) / (high - low);
   if(v < 0.0)
      return 0.0;
   if(v > 1.0)
      return 1.0;
   return v;
}

//+------------------------------------------------------------------+
string V45FavBucket(const double value)
{
   if(!ValidTelemetrySnapshot(value))
      return "NO_SNAPSHOT";
   if(value < -15.0)
      return "VERY_NEG";
   if(value < 0.0)
      return "NEG";
   if(value < 10.0)
      return "FLAT";
   if(value < 20.0)
      return "BUILDING";
   return "STRONG";
}

//+------------------------------------------------------------------+
string V45First10sMfeBucket(const double value)
{
   if(value < 5.0)
      return "DEAD";
   if(value < 15.0)
      return "WEAK";
   if(value < 40.0)
      return "MID";
   if(value < 75.0)
      return "STRONG";
   return "SPEED_LIKE";
}

//+------------------------------------------------------------------+
string V45QualityBucket(const double score)
{
   if(score >= V45FOLMHighQualityScore)
      return "HIGH";
   if(score >= V45FOLMLowQualityScore)
      return "MID";
   return "LOW";
}

//+------------------------------------------------------------------+
string V45PreEntryHighBucket(const double score)
{
   if(score >= V45PreEntryHighShadowScore)
      return "HIGH";
   if(score >= V45PreEntryMidShadowScore)
      return "MID";
   return "LOW";
}

//+------------------------------------------------------------------+
void AppendShadowSignal(string &signals, const string token)
{
   if(StringLen(token) <= 0)
      return;
   if(StringLen(signals) > 0)
      signals += "|";
   signals += token;
}

//+------------------------------------------------------------------+
void ClearV45PreEntryHighShadowLog()
{
   logV45PreEntryHighShadowScore = "";
   logV45PreEntryHighShadowBucket = "";
   logV45PreEntryHighWouldAllow = "";
   logV45PreEntryHighWouldBlock = "";
   logV45PreEntryHighSignals = "";
}

//+------------------------------------------------------------------+
void SetV45PreEntryHighShadowLog(const double score,
                                 const string bucket,
                                 const string wouldAllow,
                                 const string wouldBlock,
                                 const string signals)
{
   if(!UseV45PreEntryHighShadowTelemetry || StringLen(bucket) <= 0)
   {
      ClearV45PreEntryHighShadowLog();
      return;
   }

   logV45PreEntryHighShadowScore = DoubleToString(score, 1);
   logV45PreEntryHighShadowBucket = bucket;
   logV45PreEntryHighWouldAllow = wouldAllow;
   logV45PreEntryHighWouldBlock = wouldBlock;
   logV45PreEntryHighSignals = signals;
}

//+------------------------------------------------------------------+
void ClearV48Mode2ScorecardLog()
{
   logV48Mode2Signal = "";
   logV48Mode2BlockReason = "";
   logV48Mode2WouldAllow = "";
   logV48Mode2WouldBlock = "";
   logV48Mode2OppFlags = "";
   logV48Mode2Velocity1s = "";
   logV48Mode2WeightFactor = "";
}

//+------------------------------------------------------------------+
void SetV48Mode2ScorecardLog(const string signal,
                             const string blockReason,
                             const int oppositeFlags,
                             const double velocity1s,
                             const double weightFactor)
{
   if(!UseV48Mode2ShadowScorecard || StringLen(signal) <= 0)
   {
      ClearV48Mode2ScorecardLog();
      return;
   }

   logV48Mode2Signal = signal;
   logV48Mode2BlockReason = blockReason;
   logV48Mode2WouldAllow = (signal == "V48_MODE2_BODY_ALIGN_WOULD_ALLOW" ? "true" : "false");
   logV48Mode2WouldBlock = (signal == "V48_MODE2_BODY_ALIGN_WOULD_BLOCK" ? "true" : "false");
   logV48Mode2OppFlags = (string)oppositeFlags;
   logV48Mode2Velocity1s = DoubleToString(velocity1s, 1);
   logV48Mode2WeightFactor = DoubleToString(weightFactor, 2);
}

//+------------------------------------------------------------------+
bool V48Mode2HourBlocked()
{
   if(StringLen(V48Mode2BlockedHoursCSV) <= 0)
      return false;

   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   string parts[];
   int count = StringSplit(V48Mode2BlockedHoursCSV, (ushort)',', parts);
   for(int i = 0; i < count; i++)
   {
      int hour = (int)StringToInteger(parts[i]);
      if(hour == dt.hour)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
int V48Mode2OppositeFlags(const int side, const DirectionState &s)
{
   if(side == 0)
      return 0;

   int flags = 0;
   if(s.flowFresh && s.flowDir == -side)
      flags++;
   if(s.microDir == -side)
      flags++;
   if(s.oppositePressure)
      flags++;
   if(s.snapback)
      flags++;
   return flags;
}

//+------------------------------------------------------------------+
double V48Mode2Velocity1s(const MqlTick &t)
{
   long nowMs = (t.time_msc > 0 ? t.time_msc : GetTickMs());
   double mid = (t.ask + t.bid) * 0.5;
   return SignedVelocityPointsPerSecond(mid, nowMs, MathMax(1, V48Mode2VelocityAlignLookbackMs));
}

//+------------------------------------------------------------------+
bool V48Mode2BodyAligned(const int side, const double velocity1s)
{
   if(!V48Mode2BodyNeedsVelocityAlign)
      return true;
   if(side > 0)
      return (velocity1s > 0.0);
   if(side < 0)
      return (velocity1s < 0.0);
   return false;
}

//+------------------------------------------------------------------+
double V48Mode2WeightFactorForAction(const RouterAction action, const DirectionState &s)
{
   if(s.scenario == "BODY_WITH_TRADE_ONLY")
      return MathMax(0.0, V48Mode2BodyLotFactorForScorecard);
   return MathMax(0.0, LotFactorForAction(action, s));
}

//+------------------------------------------------------------------+
void BuildV48Mode2ShadowScorecard(const RouterAction action,
                                  const DirectionState &s,
                                  const MqlTick &t,
                                  string &signal,
                                  string &blockReason,
                                  int &oppositeFlags,
                                  double &velocity1s,
                                  double &weightFactor)
{
   signal = "";
   blockReason = "";
   oppositeFlags = 0;
   velocity1s = 0.0;
   weightFactor = 1.0;
   ClearV48Mode2ScorecardLog();

   if(!UseV48Mode2ShadowScorecard || action == ActSkip)
      return;

   int side = ActionSide(action);
   double spreadPts = 0.0;
   MqlTick latest = t;
   if(latest.ask > 0.0 && latest.bid > 0.0)
      spreadPts = (latest.ask - latest.bid) / _Point;

   velocity1s = V48Mode2Velocity1s(latest);
   oppositeFlags = V48Mode2OppositeFlags(side, s);
   weightFactor = V48Mode2WeightFactorForAction(action, s);

   bool bodyRoute = (s.scenario == "BODY_WITH_TRADE_ONLY" || s.scenario == "BODY_NOT_WITH_TRADE");
   if(V48Mode2HourBlocked())
      blockReason = "BLOCKED_HOUR";
   else if(V48Mode2MaxSpreadPoints > 0.0 && spreadPts > V48Mode2MaxSpreadPoints)
      blockReason = "SPREAD";
   else if(V48Mode2MaxOppositeFlags >= 0 && oppositeFlags > V48Mode2MaxOppositeFlags)
      blockReason = "OPPOSITE_FLAGS";
   else if(!bodyRoute)
      blockReason = "NON_BODY_ROUTE";
   else if(!V48Mode2BodyAligned(side, velocity1s))
      blockReason = "BODY_ALIGN_FAIL";

   if(StringLen(blockReason) > 0)
      signal = "V48_MODE2_BODY_ALIGN_WOULD_BLOCK";
   else
      signal = "V48_MODE2_BODY_ALIGN_WOULD_ALLOW";

   SetV48Mode2ScorecardLog(signal, blockReason, oppositeFlags, velocity1s, weightFactor);
}

//+------------------------------------------------------------------+
string V48Mode2LabelText(const string signal,
                         const string blockReason,
                         const int oppositeFlags,
                         const double velocity1s,
                         const double weightFactor)
{
   if(StringLen(signal) <= 0)
      return "";

   string label = signal +
                  ";V48_MODE2_REASON_" + (StringLen(blockReason) > 0 ? blockReason : "ALLOW") +
                  ";V48_MODE2_OPP_" + (string)oppositeFlags +
                  ";V48_MODE2_VEL1S_" + DoubleToString(velocity1s, 1) +
                  ";V48_MODE2_WEIGHT_" + DoubleToString(weightFactor, 2);
   return label;
}

//+------------------------------------------------------------------+
void BuildV45PreEntryHighShadowTelemetry(const RouterAction action,
                                         const DirectionState &s,
                                         double &score,
                                         string &bucket,
                                         string &wouldAllow,
                                         string &wouldBlock,
                                         string &signals)
{
   score = 0.0;
   bucket = "";
   wouldAllow = "";
   wouldBlock = "";
   signals = "";
   ClearV45PreEntryHighShadowLog();

   if(!UseV45PreEntryHighShadowTelemetry || action == ActSkip)
      return;

   int side = ActionSide(action);
   int winner = WinnerSide(s);
   if(side == 0 || winner == 0)
      return;

   double rawScore = 50.0;

   if(s.spreadStable)
   {
      rawScore += 10.0;
      AppendShadowSignal(signals, "SPREAD_STABLE");
   }
   else
   {
      rawScore -= 18.0;
      AppendShadowSignal(signals, "SPREAD_TRAP");
   }

   if(s.bodyDir == side && s.bodyPts >= MinCandleBodyPoints)
   {
      rawScore += 14.0;
      AppendShadowSignal(signals, "BODY_WITH");
   }
   else if(s.bodyDir == -side)
   {
      rawScore -= 12.0;
      AppendShadowSignal(signals, "BODY_AGAINST");
   }

   if(s.microDir == side)
   {
      rawScore += 14.0;
      AppendShadowSignal(signals, "MICRO_WITH");
   }
   else if(s.microDir == -side)
   {
      rawScore -= 12.0;
      AppendShadowSignal(signals, "MICRO_AGAINST");
   }

   if(s.flowAgreesWithWinner)
   {
      rawScore += 14.0;
      AppendShadowSignal(signals, "FLOW_AGREES");
   }
   else if(s.flowDisagreesWithWinner)
   {
      rawScore -= 18.0;
      AppendShadowSignal(signals, "FLOW_DISAGREES");
   }
   else if(!s.flowFresh || s.flowDir == 0)
      AppendShadowSignal(signals, "FLOW_NEUTRAL");

   if(s.oppositePressure)
   {
      rawScore -= 18.0;
      AppendShadowSignal(signals, "OPPOSITE_PRESSURE");
   }
   else
   {
      rawScore += 10.0;
      AppendShadowSignal(signals, "NO_OPPOSITE");
   }

   if(speedDir == side)
   {
      rawScore += 10.0;
      AppendShadowSignal(signals, "SPEED_WITH");
   }
   else if(speedDir == -side)
   {
      rawScore -= 14.0;
      AppendShadowSignal(signals, "SPEED_AGAINST");
   }

   if(s.follow37)
   {
      rawScore += 8.0;
      AppendShadowSignal(signals, "FOLLOW37");
   }
   else if(s.follow21)
   {
      rawScore += 5.0;
      AppendShadowSignal(signals, "FOLLOW21");
   }

   if(s.continuation)
   {
      rawScore += 6.0;
      AppendShadowSignal(signals, "CONTINUATION");
   }
   if(s.exhaustion && action != ActBuyLimit && action != ActSellLimit)
   {
      rawScore -= 12.0;
      AppendShadowSignal(signals, "EXHAUSTION_RISK");
   }

   if(preSpeedLastSignalMs > 0)
   {
      long signalAge = GetTickMs() - preSpeedLastSignalMs;
      if(signalAge >= 0 && signalAge <= PreSpeedAgainstDefenseMaxSignalAgeMs)
      {
         if(preSpeedLastSignalDir == side)
         {
            rawScore += (preSpeedLastSignalLevel >= 70 ? 7.0 : 4.0);
            AppendShadowSignal(signals, (preSpeedLastSignalLevel >= 70 ? "PRESPEED70_WITH" : "PRESPEED50_WITH"));
         }
         else if(preSpeedLastSignalDir == -side)
         {
            rawScore -= (preSpeedLastSignalLevel >= 70 ? 10.0 : 6.0);
            AppendShadowSignal(signals, (preSpeedLastSignalLevel >= 70 ? "PRESPEED70_AGAINST" : "PRESPEED50_AGAINST"));
         }
      }
   }

   double entryAdverseDeltaPts = 0.0;
   bool hasEntryDelta = LatestAdverseTickDeltaPoints(side, entryAdverseDeltaPts);
   if(hasEntryDelta && MathAbs(entryAdverseDeltaPts) >= 0.1)
   {
      if(entryAdverseDeltaPts < -0.1)
      {
         rawScore += MathMin(8.0, MathAbs(entryAdverseDeltaPts));
         AppendShadowSignal(signals, "ENTRY_JUMP_WITH");
      }
      else if(entryAdverseDeltaPts > 0.1)
      {
         rawScore -= MathMin(12.0, entryAdverseDeltaPts);
         AppendShadowSignal(signals, "ENTRY_JUMP_AGAINST");
      }
   }

   if(rawScore < 0.0)
      rawScore = 0.0;
   if(rawScore > 100.0)
      rawScore = 100.0;

   score = rawScore;
   bucket = V45PreEntryHighBucket(score);
   wouldAllow = (bucket == "HIGH" ? "true" : "false");
   wouldBlock = (bucket == "LOW" ? "true" : "false");
   SetV45PreEntryHighShadowLog(score, bucket, wouldAllow, wouldBlock, signals);
}

//+------------------------------------------------------------------+
void BuildV45FOLMQualityTelemetry(const bool isFOLM,
                                  const double finalFav,
                                  const double fav2s,
                                  const double fav3s,
                                  const double first10sMfe)
{
   logV45FOLMQualityScore = "";
   logV45FOLMQualityBucket = "";
   logV45FOLMLowQualityWouldBlock = "";
   logV45FOLMLowQualityReplayDelta = "";
   logV45FOLMFav2sBucket = "";
   logV45FOLMFav3sBucket = "";
   logV45FOLMFirst10sMfeBucket = "";

   if(!UseV45FOLMQualityTelemetry || !isFOLM)
      return;

   double fav2Score = (ValidTelemetrySnapshot(fav2s)
                       ? NormalizeRange01(fav2s, -15.0, V45FOLMFav2sTargetPoints)
                       : 0.0);
   double fav3Score = (ValidTelemetrySnapshot(fav3s)
                       ? NormalizeRange01(fav3s, -15.0, V45FOLMFav3sTargetPoints)
                       : 0.0);
   double mfeScore = NormalizeRange01(first10sMfe, 0.0, V45FOLMFirst10sMfeTargetPoints);
   double score = (fav2Score * 0.35 + fav3Score * 0.35 + mfeScore * 0.30) * 100.0;
   string bucket = V45QualityBucket(score);
   bool wouldBlock = (bucket == "LOW");

   logV45FOLMQualityScore = DoubleToString(score, 1);
   logV45FOLMQualityBucket = bucket;
   logV45FOLMLowQualityWouldBlock = (wouldBlock ? "true" : "false");
   logV45FOLMLowQualityReplayDelta = (wouldBlock ? DoubleToString(-finalFav, 1) : "0.0");
   logV45FOLMFav2sBucket = V45FavBucket(fav2s);
   logV45FOLMFav3sBucket = V45FavBucket(fav3s);
   logV45FOLMFirst10sMfeBucket = V45First10sMfeBucket(first10sMfe);
}

//+------------------------------------------------------------------+
bool LabelTextHasToken(const string labels, const string token)
{
   string haystack = ";" + labels + ";";
   string needle = ";" + token + ";";
   return (StringFind(haystack, needle) >= 0);
}

//+------------------------------------------------------------------+
bool V451LabelsHaveFlowDisagrees(const string labels)
{
   return (StringFind(labels, ":FD") >= 0 || LabelTextHasToken(labels, "FLOW_DISAGREES"));
}

//+------------------------------------------------------------------+
bool V451LabelsHaveOppositePressure(const string labels)
{
   return (LabelTextHasToken(labels, "OPPOSITE_PRESSURE") ||
           LabelTextHasToken(labels, "EXH_OPPOSITE_PRESSURE"));
}

//+------------------------------------------------------------------+
bool V451LabelsHaveFlowOppPressure(const string labels)
{
   return (V451LabelsHaveFlowDisagrees(labels) && V451LabelsHaveOppositePressure(labels));
}

//+------------------------------------------------------------------+
string V451TimingBucket(const long heldMs)
{
   if(heldMs <= 0)
      return "entry";
   if(heldMs <= 500)
      return "first500ms";
   if(heldMs <= 1000)
      return "first1s";
   if(heldMs <= 2000)
      return "first2s";
   if(heldMs <= 3000)
      return "first3s";
   return "post3s";
}

//+------------------------------------------------------------------+
void TrackV451FlowOppSource(const int idx, const long heldMs, const double fav)
{
   if(!UseV451ProofTelemetry)
      return;
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return;
   if(StringLen(trackedV451FlowOppSourceTiming[idx]) > 0)
      return;
   if(!V451LabelsHaveFlowOppPressure(trackedLabels[idx]))
      return;

   trackedV451FlowOppSourceTiming[idx] = V451TimingBucket(heldMs);
   trackedV451FlowOppSourceMs[idx] = (heldMs > 0 ? heldMs : 0);
   trackedV451FlowOppSourceFav[idx] = fav;
}

//+------------------------------------------------------------------+
void ClearV451ProofTelemetryLog()
{
   logV451LowJFirst1sFired = "";
   logV451LowJFirst1sMs = 0;
   logV451LowJFirst1sFav = 0.0;
   logV451LowJFirst1sReplayDelta = 0.0;
   logV451LowJFirst1sLeadMs = 0;
   logV451LowJFirst1sBeforeCurrentShield = "";
   logV451LowJFirst2sFired = "";
   logV451LowJFirst2sMs = 0;
   logV451LowJFirst2sFav = 0.0;
   logV451LowJFirst2sReplayDelta = 0.0;
   logV451LowJFirst2sLeadMs = 0;
   logV451LowJFirst2sBeforeCurrentShield = "";
   logV451ActualCloseEvent = "";
   logV451ActualCloseFav = 0.0;
   logV451ActualCloseHeldMs = 0;
   logV451FlowOppAuditFlag = "";
   logV451FlowOppSourceTiming = "";
   logV451FlowOppSourceMs = 0;
   logV451FlowOppSourceFav = 0.0;
}

//+------------------------------------------------------------------+
void ClearV452LowWinnerMicroscopeLog()
{
   logV452LowMicroscopeActive = "";
   logV452LowFinalPath = "";
   logV452LowEntryRoute = "";
   logV452LowRecoveryProfile = "";
   logV452LowFav1ToFav3Delta = "";
   logV452LowFav2ToFav3Delta = "";
   logV452LowMaxFav1To3 = "";
   logV452LowHad1sAdverseJump = "";
   logV452LowHad2sAdverseJump = "";
   logV452LowJumpRecoveredBy3s = "";
   logV452LowJumpRecoveredToSpeed = "";
   logV452LowPressureActionable = "";
   logV452LowPressureBefore3s = "";
   logV452LowEscapeReason = "";
   logV452LowKillRiskFlag = "";
   logV452LowDeadStrict = "";
}

//+------------------------------------------------------------------+
void ClearV46LowDeadShadowReplayLog()
{
   logV46LowDeadShadowFired = "";
   logV46LowDeadShadowMs = 0;
   logV46LowDeadShadowFav = 0.0;
   logV46LowDeadShadowMfe = 0.0;
   logV46LowDeadShadowMaxFav1To3 = 0.0;
   logV46LowDeadShadowReplayDelta = 0.0;
   logV46LowDeadShadowLeadMs = 0;
   logV46LowDeadShadowBeforeCurrentShield = "";
   logV46LowDeadShadowFinalPath = "";
   logV46LowDeadShadowSpeedTouched = "";
   logV46LowDeadShadowReason = "";
}

//+------------------------------------------------------------------+
void ClearV461MicroTelemetryLog()
{
   logV461FavAt250ms = "";
   logV461FavAt500ms = "";
   logV461TimeToFirstProfitMs = "";
   logV461TimeToMfe10Ms = "";
   logV461TimeToMfe20Ms = "";
   logV461TimeToMfe40Ms = "";
   logV461MfeSlope1sTo3s = "";
   logV461MaxPullbackAfterFirstProfit = "";
   logV461HighMidMicroClass = "";
   logV461HighMidTimeToSpeedMs = "";
   logV461HighMidFailedReason = "";
   logV461LowDetectMs = "";
   logV461LowDetectFav = "";
   logV461LowDetectSpread = "";
   logV461LowDetectOrderflowState = "";
   logV461LowDetectPressureState = "";
   logV461OppAtEntryMfe = "";
   logV461OppAtEntryMae = "";
   logV461OppAtEntryWouldSpeed = "";
   logV461OppAtEntryNetDelta = "";
   logV461OppAtLowMfe = "";
   logV461OppAtLowMae = "";
   logV461OppAtLowWouldSpeed = "";
   logV461OppAtLowWouldHardLose = "";
   logV461OppAtLowNetDelta = "";
   logV461LowMicroClass = "";
   logV461LowMicroClassReason = "";
}

//+------------------------------------------------------------------+
void ClearV47DecisionFrontierLog()
{
   logV47BucketPresent = "";
   logV47BucketNullReason = "";
   logV47BucketAuditCloseReason = "";
   logV47BucketAuditRoute = "";
   logV47BucketAuditSession = "";
   logV47BucketAuditSpread = "";
   logV47BucketAuditFinalPath = "";
   logV47EntryAvoidShadow = "";
   logV47500msAvoidShadow = "";
   logV471sAvoidShadow = "";
   logV472sAvoidShadow = "";
   logV473sAvoidShadow = "";
   logV47FirstAvoidTimeMs = "";
   logV47FirstAvoidStage = "";
   logV47AvoidReason = "";
   logV47AvoidReplayDelta = "";
   logV47WouldBlockLowNoTrade = "";
   logV47WouldBlockLowUnresolved = "";
   logV47WouldBlockHigh = "";
   logV47WouldBlockMid = "";
   logV47WouldBlockSpeed = "";
   logV47PreEntryShadowScore = "";
   logV47PreEntryShadowBucket = "";
   logV47PreEntryShadowSignals = "";
   logV47TimeToFirstFavorableTickMs = "";
   logV47First500msAdverseJump = "";
   logV47First1sAdverseJump = "";
   logV47First2sAdverseJump = "";
   logV47FrontierNotes = "";

   logV471SchemaVersion = "";
   logV471RouteScope = "";
   logV471Alive100ms = "";
   logV471Alive250ms = "";
   logV471Alive500ms = "";
   logV471Alive750ms = "";
   logV471Alive1s = "";
   logV471Alive1500ms = "";
   logV471Alive2s = "";
   logV471Alive3s = "";
   logV471Sample100ms = "";
   logV471Sample250ms = "";
   logV471Sample500ms = "";
   logV471Sample750ms = "";
   logV471Sample1s = "";
   logV471Sample1500ms = "";
   logV471Sample2s = "";
   logV471Sample3s = "";
   logV471Fav100ms = "";
   logV471Fav250ms = "";
   logV471Fav500ms = "";
   logV471Fav750ms = "";
   logV471Fav1s = "";
   logV471Fav1500ms = "";
   logV471Fav2s = "";
   logV471Fav3s = "";
   logV471Ticks100ms = "";
   logV471Ticks250ms = "";
   logV471Ticks500ms = "";
   logV471Ticks750ms = "";
   logV471Ticks1s = "";
   logV471Ticks1500ms = "";
   logV471Ticks2s = "";
   logV471Ticks3s = "";
   logV471First250msAdverseJump = "";
   logV471First500msAdverseJump = "";
   logV471First750msAdverseJump = "";
   logV471First1sAdverseJump = "";
   logV471First2sAdverseJump = "";
   logV471TickPath1to8 = "";
   logV471PreEntryTapeHealth = "";
   logV471PreEntryVelocityDecay = "";
   logV471PreSpeedSignalAgeMs = "";
   logV471FirstFavorableTickState = "";
   logV471EntryAvoidShadow = "";
   logV471250msAvoidShadow = "";
   logV471500msAvoidShadow = "";
   logV471750msAvoidShadow = "";
   logV4711sAvoidShadow = "";
   logV471FirstAvoidTimeMs = "";
   logV471FirstAvoidStage = "";
   logV471AvoidReason = "";
   logV471AvoidReplayDelta = "";
   logV471WouldBlockLowNoTrade = "";
   logV471WouldBlockLowUnresolved = "";
   logV471WouldBlockHigh = "";
   logV471WouldBlockMid = "";
   logV471WouldBlockSpeed = "";
   logV471CoverageNote = "";
}

//+------------------------------------------------------------------+
string V461OrderflowStateName(const string labels)
{
   if(V451LabelsHaveFlowDisagrees(labels))
      return "FLOW_DISAGREES";
   if(StringFind(labels, ":FA") >= 0 || LabelTextHasToken(labels, "FLOW_AGREES"))
      return "FLOW_AGREES";
   return "FLOW_NEUTRAL_OR_UNKNOWN";
}

//+------------------------------------------------------------------+
string V461PressureStateName(const string labels)
{
   if(V451LabelsHaveOppositePressure(labels))
      return "OPPOSITE_PRESSURE";
   if(LabelTextHasToken(labels, "NO_OPPOSITE_PRESSURE") || LabelTextHasToken(labels, "BODY_NO_OPPOSITE"))
      return "NO_OPPOSITE_PRESSURE";
   return "PRESSURE_UNKNOWN";
}

//+------------------------------------------------------------------+
string V461HighMidFailureReason(const string finalPath,
                                const double first10sMfe,
                                const double maxPullback,
                                const string orderflowState,
                                const string pressureState)
{
   if(finalPath == "SPEED")
      return "";
   if(first10sMfe < V461Mfe20LevelPoints)
      return "NO_EXPANSION";
   if(maxPullback >= V461Mfe20LevelPoints)
      return "PULLBACK_AFTER_PROFIT";
   if(orderflowState == "FLOW_DISAGREES")
      return "FLOW_DISAGREED";
   if(pressureState == "OPPOSITE_PRESSURE")
      return "OPPOSITE_PRESSURE";
   return "FAILED_AFTER_GOOD_START";
}

//+------------------------------------------------------------------+
string V461HighMidMicroClass(const string qualityBucket,
                             const string finalPath,
                             const long timeToMfe40Ms,
                             const long timeToSpeedMs,
                             const double first10sMfe,
                             const double maxPullback)
{
   if(qualityBucket != "HIGH" && qualityBucket != "MID")
      return "";

   if(qualityBucket == "HIGH" && finalPath == "SPEED")
   {
      if((timeToMfe40Ms > 0 && timeToMfe40Ms <= 3000) ||
         (timeToSpeedMs > 0 && timeToSpeedMs <= 5000))
         return "HIGH_FAST_SPEED";
      return "HIGH_SPEED_BUILDER";
   }

   if(qualityBucket == "MID" && finalPath == "SPEED")
      return "MID_BUILDING";

   if(qualityBucket == "HIGH" && finalPath != "SPEED")
      return "HIGH_FAKE_START";

   if(qualityBucket == "MID" && finalPath != "SPEED")
   {
      if(first10sMfe >= V461Mfe40LevelPoints && maxPullback >= V461Mfe20LevelPoints)
         return "MID_PULLBACK_FAIL";
      return "MID_STALL";
   }

   return "";
}

//+------------------------------------------------------------------+
void BuildV461MicroTelemetry(const int idx,
                             const bool isFOLM,
                             const string eventTag,
                             const double finalFav,
                             const long heldMs,
                             const string labels,
                             const string qualityBucket)
{
   ClearV461MicroTelemetryLog();

   if(!UseV461MicroTelemetry || !isFOLM || idx < 0 || idx >= ArraySize(trackedTickets))
      return;

   string finalPath = V452FinalPathName(eventTag, finalFav);
   string orderflowState = V461OrderflowStateName(labels);
   string pressureState = V461PressureStateName(labels);

   if(ValidTelemetrySnapshot(trackedFavAt250ms[idx]))
      logV461FavAt250ms = DoubleToString(trackedFavAt250ms[idx], 1);
   if(ValidTelemetrySnapshot(trackedFavAt500ms[idx]))
      logV461FavAt500ms = DoubleToString(trackedFavAt500ms[idx], 1);
   if(trackedTimeToFirstProfitMs[idx] > 0)
      logV461TimeToFirstProfitMs = (string)trackedTimeToFirstProfitMs[idx];
   if(trackedTimeToMfe10Ms[idx] > 0)
      logV461TimeToMfe10Ms = (string)trackedTimeToMfe10Ms[idx];
   if(trackedTimeToMfe20Ms[idx] > 0)
      logV461TimeToMfe20Ms = (string)trackedTimeToMfe20Ms[idx];
   if(trackedTimeToMfe40Ms[idx] > 0)
      logV461TimeToMfe40Ms = (string)trackedTimeToMfe40Ms[idx];
   if(ValidTelemetrySnapshot(trackedFavAt1s[idx]) && ValidTelemetrySnapshot(trackedFavAt3s[idx]))
      logV461MfeSlope1sTo3s = DoubleToString((trackedFavAt3s[idx] - trackedFavAt1s[idx]) / 2.0, 2);
   logV461MaxPullbackAfterFirstProfit = DoubleToString(trackedMaxPullbackAfterFirstProfit[idx], 1);

   string highMidClass = V461HighMidMicroClass(qualityBucket,
                                               finalPath,
                                               trackedTimeToMfe40Ms[idx],
                                               trackedTimeToSpeedMs[idx],
                                               trackedFirst10sMfes[idx],
                                               trackedMaxPullbackAfterFirstProfit[idx]);
   logV461HighMidMicroClass = highMidClass;
   if(qualityBucket == "HIGH" || qualityBucket == "MID")
   {
      if(trackedTimeToSpeedMs[idx] > 0)
         logV461HighMidTimeToSpeedMs = (string)trackedTimeToSpeedMs[idx];
      logV461HighMidFailedReason = V461HighMidFailureReason(finalPath,
                                                            trackedFirst10sMfes[idx],
                                                            trackedMaxPullbackAfterFirstProfit[idx],
                                                            orderflowState,
                                                            pressureState);
   }

   if(qualityBucket != "LOW")
      return;

   double oppEntryMfe = MathMax(0.0, -trackedMaes[idx]);
   double oppEntryMae = -MathMax(0.0, trackedMfes[idx]);
   bool oppEntryWouldSpeed = (V461OppositeSpeedPoints > 0.0 && oppEntryMfe >= V461OppositeSpeedPoints);
   double oppEntryTerminal = (oppEntryWouldSpeed ? V461OppositeSpeedPoints : -finalFav);
   double oppEntryNetDelta = oppEntryTerminal - finalFav;

   logV461OppAtEntryMfe = DoubleToString(oppEntryMfe, 1);
   logV461OppAtEntryMae = DoubleToString(oppEntryMae, 1);
   logV461OppAtEntryWouldSpeed = V452BoolText(oppEntryWouldSpeed);
   logV461OppAtEntryNetDelta = DoubleToString(oppEntryNetDelta, 1);

   bool lowDetected = trackedV46LowDeadShadowFired[idx];
   bool oppLowWouldSpeed = false;
   bool oppLowWouldHardLose = false;
   if(lowDetected)
   {
      oppLowWouldSpeed = trackedV461OppAtLowWouldSpeed[idx];
      oppLowWouldHardLose = trackedV461OppAtLowWouldHardLose[idx];
      double oppLowTerminal = (oppLowWouldSpeed ? V461OppositeSpeedPoints : trackedV46LowDeadShadowFav[idx] - finalFav);
      if(oppLowWouldHardLose && !oppLowWouldSpeed)
         oppLowTerminal = -V461OppositeHardLossPoints;
      double oppLowNetDelta = oppLowTerminal - finalFav;

      logV461LowDetectMs = (string)trackedV46LowDeadShadowMs[idx];
      logV461LowDetectFav = DoubleToString(trackedV46LowDeadShadowFav[idx], 1);
      logV461LowDetectSpread = DoubleToString(trackedV461LowDetectSpread[idx], 1);
      logV461LowDetectOrderflowState = trackedV461LowDetectOrderflowState[idx];
      logV461LowDetectPressureState = trackedV461LowDetectPressureState[idx];
      logV461OppAtLowMfe = DoubleToString(trackedV461OppAtLowMfe[idx], 1);
      logV461OppAtLowMae = DoubleToString(trackedV461OppAtLowMae[idx], 1);
      logV461OppAtLowWouldSpeed = V452BoolText(oppLowWouldSpeed);
      logV461OppAtLowWouldHardLose = V452BoolText(oppLowWouldHardLose);
      logV461OppAtLowNetDelta = DoubleToString(oppLowNetDelta, 1);
   }

   if(finalPath == "SPEED")
   {
      logV461LowMicroClass = "LOW_FALSE_ALARM";
      logV461LowMicroClassReason = "LOW_REACHED_SPEED";
   }
   else if(lowDetected && oppLowWouldSpeed)
   {
      logV461LowMicroClass = "LOW_TRUE_INVERSE";
      logV461LowMicroClassReason = "OPPOSITE_AT_LOW_WOULD_SPEED";
   }
   else if(oppEntryWouldSpeed && (!lowDetected || !oppLowWouldSpeed))
   {
      logV461LowMicroClass = "LOW_TOO_LATE";
      logV461LowMicroClassReason = "OPPOSITE_AT_ENTRY_ONLY";
   }
   else if(finalFav < 0.0 && !oppEntryWouldSpeed && (!lowDetected || !oppLowWouldSpeed))
   {
      logV461LowMicroClass = "LOW_NO_TRADE";
      logV461LowMicroClassReason = (lowDetected ? "BOTH_DIRECTIONS_FAILED_AFTER_LOW" : "NO_LOW_DETECT_BOTH_WEAK");
   }
   else
   {
      logV461LowMicroClass = "LOW_UNRESOLVED";
      logV461LowMicroClassReason = "NEEDS_MORE_PATH_DATA";
   }
}

//+------------------------------------------------------------------+
bool V47StageEnabled(const int stageMs)
{
   return (V47DecisionFrontierMaxMs <= 0 || stageMs <= V47DecisionFrontierMaxMs);
}

//+------------------------------------------------------------------+
bool V47FirstProfitBy(const int idx, const int stageMs)
{
   if(idx < 0 || idx >= ArraySize(trackedTimeToFirstProfitMs))
      return false;
   return (trackedTimeToFirstProfitMs[idx] > 0 && trackedTimeToFirstProfitMs[idx] <= stageMs);
}

//+------------------------------------------------------------------+
void RecordFirstProfitTelemetry(const int idx,
                                const long heldMs,
                                const double fav,
                                const bool closeBackfill)
{
   if(idx < 0 || idx >= ArraySize(trackedTimeToFirstProfitMs))
      return;
   if(fav <= 0.0)
      return;

   long seenMs = (heldMs > 0 ? heldMs : 1);
   if(!trackedFirstProfitSeen[idx] || trackedTimeToFirstProfitMs[idx] <= 0)
   {
      trackedFirstProfitSeen[idx] = true;
      trackedTimeToFirstProfitMs[idx] = seenMs;
      trackedPeakAfterFirstProfit[idx] = fav;
      if(closeBackfill && !TrackedLabelHas(idx, "V471_FIRST_FAVORABLE_CLOSE_BACKFILL"))
         trackedLabels[idx] += ";V471_FIRST_FAVORABLE_CLOSE_BACKFILL";
   }

   if(trackedFirstProfitSeen[idx])
   {
      if(fav > trackedPeakAfterFirstProfit[idx])
         trackedPeakAfterFirstProfit[idx] = fav;
      double pullback = trackedPeakAfterFirstProfit[idx] - fav;
      if(pullback > trackedMaxPullbackAfterFirstProfit[idx])
         trackedMaxPullbackAfterFirstProfit[idx] = pullback;
   }
}

//+------------------------------------------------------------------+
int V471TickCapsuleLimit()
{
   int limit = V471TickCapsuleCount;
   if(limit < 0)
      limit = 0;
   if(limit > 8)
      limit = 8;
   return limit;
}

//+------------------------------------------------------------------+
int V471TickCountSince(const long nowMs, const int lookbackMs)
{
   int count = 0;
   long fromMs = nowMs - MathMax(1, lookbackMs);
   for(int i = ArraySize(tickMs) - 1; i >= 0; i--)
   {
      if(tickMs[i] > nowMs)
         continue;
      if(tickMs[i] < fromMs)
         break;
      count++;
   }
   return count;
}

//+------------------------------------------------------------------+
long V471MaxTickGapSince(const long nowMs, const int lookbackMs)
{
   long fromMs = nowMs - MathMax(1, lookbackMs);
   long lastMs = 0;
   long maxGap = 0;
   for(int i = 0; i < ArraySize(tickMs); i++)
   {
      if(tickMs[i] < fromMs || tickMs[i] > nowMs)
         continue;
      if(lastMs > 0)
      {
         long gap = tickMs[i] - lastMs;
         if(gap > maxGap)
            maxGap = gap;
      }
      lastMs = tickMs[i];
   }
   return maxGap;
}

//+------------------------------------------------------------------+
long V471PreSpeedSignalAgeMs(const long nowMs)
{
   if(preSpeedLastSignalMs <= 0)
      return -1;
   long age = nowMs - preSpeedLastSignalMs;
   return (age >= 0 ? age : -1);
}

//+------------------------------------------------------------------+
string V471BuildPreEntryTapeHealth(const MqlTick &t)
{
   long nowMs = (t.time_msc > 0 ? t.time_msc : GetTickMs());
   double spreadPts = (t.ask - t.bid) / _Point;
   return "ticks250=" + (string)V471TickCountSince(nowMs, 250) +
          ";ticks500=" + (string)V471TickCountSince(nowMs, 500) +
          ";ticks1000=" + (string)V471TickCountSince(nowMs, 1000) +
          ";maxgap1000=" + (string)V471MaxTickGapSince(nowMs, 1000) +
          ";spread=" + DoubleToString(spreadPts, 1) +
          ";regime=" + SpreadRegimeName(spreadPts);
}

//+------------------------------------------------------------------+
double V471PreEntryVelocityDecay(const MqlTick &t)
{
   long nowMs = (t.time_msc > 0 ? t.time_msc : GetTickMs());
   double mid = (t.ask + t.bid) * 0.5;
   return SignedVelocityPointsPerSecond(mid, nowMs, 1000) -
          SignedVelocityPointsPerSecond(mid, nowMs, 3000);
}

//+------------------------------------------------------------------+
string V471SnapshotText(const bool alive, const double value)
{
   if(!alive || !ValidTelemetrySnapshot(value))
      return "";
   return DoubleToString(value, 1);
}

//+------------------------------------------------------------------+
string V471IntText(const bool alive, const int value)
{
   if(!alive)
      return "";
   return (string)value;
}

//+------------------------------------------------------------------+
string V471LongText(const bool alive, const long value)
{
   if(!alive || value <= 0)
      return "";
   return (string)value;
}

//+------------------------------------------------------------------+
void V471TrackStageSnapshots(const int idx, const long heldMs, const double fav)
{
   if(!UseV471TelemetryRepair || idx < 0 || idx >= ArraySize(trackedTickets))
      return;

   if(heldMs >= 100 && !trackedAliveAt100ms[idx])
   {
      trackedAliveAt100ms[idx] = true;
      trackedFavAt100ms[idx] = fav;
      trackedTicksAt100ms[idx] = trackedTickCounts[idx];
      trackedSampleMsAt100ms[idx] = heldMs;
   }
   if(heldMs >= 250 && !trackedAliveAt250ms[idx])
   {
      trackedAliveAt250ms[idx] = true;
      trackedFavAt250ms[idx] = fav;
      trackedTicksAt250ms[idx] = trackedTickCounts[idx];
      trackedSampleMsAt250ms[idx] = heldMs;
   }
   if(heldMs >= 500 && !trackedAliveAt500ms[idx])
   {
      trackedAliveAt500ms[idx] = true;
      trackedFavAt500ms[idx] = fav;
      trackedTicksAt500ms[idx] = trackedTickCounts[idx];
      trackedSampleMsAt500ms[idx] = heldMs;
   }
   if(heldMs >= 750 && !trackedAliveAt750ms[idx])
   {
      trackedAliveAt750ms[idx] = true;
      trackedFavAt750ms[idx] = fav;
      trackedTicksAt750ms[idx] = trackedTickCounts[idx];
      trackedSampleMsAt750ms[idx] = heldMs;
   }
   if(heldMs >= 1000 && !trackedAliveAt1s[idx])
   {
      trackedAliveAt1s[idx] = true;
      trackedFavAt1s[idx] = fav;
      trackedTicksAt1s[idx] = trackedTickCounts[idx];
      trackedSampleMsAt1s[idx] = heldMs;
   }
   if(heldMs >= 1500 && !trackedAliveAt1500ms[idx])
   {
      trackedAliveAt1500ms[idx] = true;
      trackedFavAt1500ms[idx] = fav;
      trackedTicksAt1500ms[idx] = trackedTickCounts[idx];
      trackedSampleMsAt1500ms[idx] = heldMs;
   }
   if(heldMs >= 2000 && !trackedAliveAt2s[idx])
   {
      trackedAliveAt2s[idx] = true;
      trackedFavAt2s[idx] = fav;
      trackedTicksAt2s[idx] = trackedTickCounts[idx];
      trackedSampleMsAt2s[idx] = heldMs;
   }
   if(heldMs >= 3000 && !trackedAliveAt3s[idx])
   {
      trackedAliveAt3s[idx] = true;
      trackedFavAt3s[idx] = fav;
      trackedTicksAt3s[idx] = trackedTickCounts[idx];
      trackedSampleMsAt3s[idx] = heldMs;
   }
}

//+------------------------------------------------------------------+
void V471AppendTickCapsule(const int idx,
                           const long heldMs,
                           const double fav,
                           const double adverseDeltaPts,
                           const double spreadPts)
{
   if(!UseV471TelemetryRepair || idx < 0 || idx >= ArraySize(trackedTickets))
      return;
   if(trackedTickCounts[idx] <= 0 || trackedTickCounts[idx] > V471TickCapsuleLimit())
      return;

   string capsule = "tick=" + (string)trackedTickCounts[idx] +
                    ":ms=" + (string)heldMs +
                    ":fav=" + DoubleToString(fav, 1) +
                    ":adverse=" + DoubleToString(adverseDeltaPts, 1) +
                    ":spread=" + DoubleToString(spreadPts, 1);
   if(StringLen(trackedV471TickPath[idx]) > 0)
      trackedV471TickPath[idx] += ";";
   trackedV471TickPath[idx] += capsule;
}

//+------------------------------------------------------------------+
void BuildV471TelemetryRepair(const int idx,
                              const bool isFOLM,
                              const string eventTag,
                              const double finalFav,
                              const long heldMs,
                              const string qualityBucket)
{
   if(!UseV471TelemetryRepair)
      return;

   logV471SchemaVersion = "v47.1.3";
   logV471RouteScope = "ALL_ROUTES";

   bool validIdx = (idx >= 0 && idx < ArraySize(trackedTickets));
   if(!validIdx)
   {
      logV471CoverageNote = "NO_TRACKED_TICKET";
      return;
   }

   string finalPath = V452FinalPathName(eventTag, finalFav);
   string notes = (isFOLM ? "FOLM_ROUTE" : "NON_FOLM_ROUTE");

   logV471Alive100ms = V452BoolText(trackedAliveAt100ms[idx]);
   logV471Alive250ms = V452BoolText(trackedAliveAt250ms[idx]);
   logV471Alive500ms = V452BoolText(trackedAliveAt500ms[idx]);
   logV471Alive750ms = V452BoolText(trackedAliveAt750ms[idx]);
   logV471Alive1s = V452BoolText(trackedAliveAt1s[idx]);
   logV471Alive1500ms = V452BoolText(trackedAliveAt1500ms[idx]);
   logV471Alive2s = V452BoolText(trackedAliveAt2s[idx]);
   logV471Alive3s = V452BoolText(trackedAliveAt3s[idx]);

   logV471Sample100ms = V471LongText(trackedAliveAt100ms[idx], trackedSampleMsAt100ms[idx]);
   logV471Sample250ms = V471LongText(trackedAliveAt250ms[idx], trackedSampleMsAt250ms[idx]);
   logV471Sample500ms = V471LongText(trackedAliveAt500ms[idx], trackedSampleMsAt500ms[idx]);
   logV471Sample750ms = V471LongText(trackedAliveAt750ms[idx], trackedSampleMsAt750ms[idx]);
   logV471Sample1s = V471LongText(trackedAliveAt1s[idx], trackedSampleMsAt1s[idx]);
   logV471Sample1500ms = V471LongText(trackedAliveAt1500ms[idx], trackedSampleMsAt1500ms[idx]);
   logV471Sample2s = V471LongText(trackedAliveAt2s[idx], trackedSampleMsAt2s[idx]);
   logV471Sample3s = V471LongText(trackedAliveAt3s[idx], trackedSampleMsAt3s[idx]);

   logV471Fav100ms = V471SnapshotText(trackedAliveAt100ms[idx], trackedFavAt100ms[idx]);
   logV471Fav250ms = V471SnapshotText(trackedAliveAt250ms[idx], trackedFavAt250ms[idx]);
   logV471Fav500ms = V471SnapshotText(trackedAliveAt500ms[idx], trackedFavAt500ms[idx]);
   logV471Fav750ms = V471SnapshotText(trackedAliveAt750ms[idx], trackedFavAt750ms[idx]);
   logV471Fav1s = V471SnapshotText(trackedAliveAt1s[idx], trackedFavAt1s[idx]);
   logV471Fav1500ms = V471SnapshotText(trackedAliveAt1500ms[idx], trackedFavAt1500ms[idx]);
   logV471Fav2s = V471SnapshotText(trackedAliveAt2s[idx], trackedFavAt2s[idx]);
   logV471Fav3s = V471SnapshotText(trackedAliveAt3s[idx], trackedFavAt3s[idx]);

   logV471Ticks100ms = V471IntText(trackedAliveAt100ms[idx], trackedTicksAt100ms[idx]);
   logV471Ticks250ms = V471IntText(trackedAliveAt250ms[idx], trackedTicksAt250ms[idx]);
   logV471Ticks500ms = V471IntText(trackedAliveAt500ms[idx], trackedTicksAt500ms[idx]);
   logV471Ticks750ms = V471IntText(trackedAliveAt750ms[idx], trackedTicksAt750ms[idx]);
   logV471Ticks1s = V471IntText(trackedAliveAt1s[idx], trackedTicksAt1s[idx]);
   logV471Ticks1500ms = V471IntText(trackedAliveAt1500ms[idx], trackedTicksAt1500ms[idx]);
   logV471Ticks2s = V471IntText(trackedAliveAt2s[idx], trackedTicksAt2s[idx]);
   logV471Ticks3s = V471IntText(trackedAliveAt3s[idx], trackedTicksAt3s[idx]);

   logV471First250msAdverseJump = DoubleToString(trackedFirst250msMaxAdverseJumpPts[idx], 1);
   logV471First500msAdverseJump = DoubleToString(trackedFirst500msMaxAdverseJumpPts[idx], 1);
   logV471First750msAdverseJump = DoubleToString(trackedFirst750msMaxAdverseJumpPts[idx], 1);
   logV471First1sAdverseJump = DoubleToString(trackedFirst1sMaxAdverseJumpPts[idx], 1);
   logV471First2sAdverseJump = DoubleToString(trackedFirst2sMaxAdverseJumpPts[idx], 1);
   logV471TickPath1to8 = trackedV471TickPath[idx];
   logV471PreEntryTapeHealth = trackedV471PreEntryTapeHealth[idx];
   logV471PreEntryVelocityDecay = DoubleToString(trackedV471PreEntryVelocityDecay[idx], 1);
   logV471PreSpeedSignalAgeMs = (trackedV471PreSpeedSignalAgeMs[idx] >= 0 ? (string)trackedV471PreSpeedSignalAgeMs[idx] : "");
   if(trackedTimeToFirstProfitMs[idx] > 0 && StringLen(logV47TimeToFirstFavorableTickMs) <= 0)
      logV47TimeToFirstFavorableTickMs = (string)trackedTimeToFirstProfitMs[idx];
   logV471FirstFavorableTickState = (trackedTimeToFirstProfitMs[idx] > 0
                                     ? (TrackedLabelHas(idx, "V471_FIRST_FAVORABLE_CLOSE_BACKFILL")
                                        ? "SEEN_BY_CLOSE_MS_" + (string)trackedTimeToFirstProfitMs[idx]
                                        : "SEEN_MS_" + (string)trackedTimeToFirstProfitMs[idx])
                                     : "NEVER_SEEN_BY_CLOSE");

   bool avoid250 = (trackedAliveAt250ms[idx] &&
                    trackedFavAt250ms[idx] <= V471EarlyFavCeilingPoints &&
                    !V47FirstProfitBy(idx, 250) &&
                    (trackedFirst250msMaxAdverseJumpPts[idx] >= V471AdverseJumpPoints ||
                     trackedTicksAt250ms[idx] <= V471TapeDeadMaxTicks500ms));
   bool avoid500 = (trackedAliveAt500ms[idx] &&
                    trackedFavAt500ms[idx] <= V471EarlyFavCeilingPoints &&
                    !V47FirstProfitBy(idx, 500) &&
                    (trackedFirst500msMaxAdverseJumpPts[idx] >= V471AdverseJumpPoints ||
                     trackedTicksAt500ms[idx] <= V471TapeDeadMaxTicks500ms));
   bool avoid750 = (trackedAliveAt750ms[idx] &&
                    trackedFavAt750ms[idx] <= V471EarlyFavCeilingPoints &&
                    !V47FirstProfitBy(idx, 750) &&
                    (trackedFirst750msMaxAdverseJumpPts[idx] >= V471AdverseJumpPoints ||
                     trackedTicksAt750ms[idx] <= V471TapeDeadMaxTicks1000ms));
   bool avoid1s = (trackedAliveAt1s[idx] &&
                   trackedFavAt1s[idx] <= V471EarlyFavCeilingPoints &&
                   !V47FirstProfitBy(idx, 1000) &&
                   (trackedFirst1sMaxAdverseJumpPts[idx] >= V471AdverseJumpPoints ||
                    trackedTicksAt1s[idx] <= V471TapeDeadMaxTicks1000ms));

   logV471EntryAvoidShadow = "false";
   logV471250msAvoidShadow = (trackedAliveAt250ms[idx] ? V452BoolText(avoid250) : "");
   logV471500msAvoidShadow = (trackedAliveAt500ms[idx] ? V452BoolText(avoid500) : "");
   logV471750msAvoidShadow = (trackedAliveAt750ms[idx] ? V452BoolText(avoid750) : "");
   logV4711sAvoidShadow = (trackedAliveAt1s[idx] ? V452BoolText(avoid1s) : "");

   bool firstAvoid = false;
   double firstAvoidFav = 0.0;
   long firstAvoidMs = 0;
   string avoidReason = "";

   if(avoid250)
   {
      firstAvoid = true;
      firstAvoidFav = trackedFavAt250ms[idx];
      firstAvoidMs = trackedSampleMsAt250ms[idx];
      logV471FirstAvoidStage = "250MS";
      AppendShadowSignal(avoidReason, "NO_FAVORABLE_BY_250MS");
      if(trackedFirst250msMaxAdverseJumpPts[idx] >= V471AdverseJumpPoints)
         AppendShadowSignal(avoidReason, "ADVERSE_250MS_GE_THRESHOLD");
      if(trackedTicksAt250ms[idx] <= V471TapeDeadMaxTicks500ms)
         AppendShadowSignal(avoidReason, "TAPE_DEAD_250MS");
   }
   if(!firstAvoid && avoid500)
   {
      firstAvoid = true;
      firstAvoidFav = trackedFavAt500ms[idx];
      firstAvoidMs = trackedSampleMsAt500ms[idx];
      logV471FirstAvoidStage = "500MS";
      AppendShadowSignal(avoidReason, "NO_FAVORABLE_BY_500MS");
      if(trackedFirst500msMaxAdverseJumpPts[idx] >= V471AdverseJumpPoints)
         AppendShadowSignal(avoidReason, "ADVERSE_500MS_GE_THRESHOLD");
      if(trackedTicksAt500ms[idx] <= V471TapeDeadMaxTicks500ms)
         AppendShadowSignal(avoidReason, "TAPE_DEAD_500MS");
   }
   if(!firstAvoid && avoid750)
   {
      firstAvoid = true;
      firstAvoidFav = trackedFavAt750ms[idx];
      firstAvoidMs = trackedSampleMsAt750ms[idx];
      logV471FirstAvoidStage = "750MS";
      AppendShadowSignal(avoidReason, "NO_FAVORABLE_BY_750MS");
      if(trackedFirst750msMaxAdverseJumpPts[idx] >= V471AdverseJumpPoints)
         AppendShadowSignal(avoidReason, "ADVERSE_750MS_GE_THRESHOLD");
      if(trackedTicksAt750ms[idx] <= V471TapeDeadMaxTicks1000ms)
         AppendShadowSignal(avoidReason, "TAPE_DEAD_750MS");
   }
   if(!firstAvoid && avoid1s)
   {
      firstAvoid = true;
      firstAvoidFav = trackedFavAt1s[idx];
      firstAvoidMs = trackedSampleMsAt1s[idx];
      logV471FirstAvoidStage = "1S";
      AppendShadowSignal(avoidReason, "NO_FAVORABLE_BY_1S");
      if(trackedFirst1sMaxAdverseJumpPts[idx] >= V471AdverseJumpPoints)
         AppendShadowSignal(avoidReason, "ADVERSE_1S_GE_THRESHOLD");
      if(trackedTicksAt1s[idx] <= V471TapeDeadMaxTicks1000ms)
         AppendShadowSignal(avoidReason, "TAPE_DEAD_1S");
   }

   if(firstAvoid)
   {
      logV471FirstAvoidTimeMs = (string)firstAvoidMs;
      logV471AvoidReason = avoidReason;
      logV471AvoidReplayDelta = DoubleToString(firstAvoidFav - finalFav, 1);
   }

   bool blocksLowNoTrade = (firstAvoid && logV461LowMicroClass == "LOW_NO_TRADE");
   bool blocksLowUnresolved = (firstAvoid &&
                               (logV461LowMicroClass == "LOW_UNRESOLVED" ||
                                logV461LowMicroClass == "LOW_FALSE_ALARM"));
   bool blocksHigh = (firstAvoid && qualityBucket == "HIGH");
   bool blocksMid = (firstAvoid && qualityBucket == "MID");
   bool blocksSpeed = (firstAvoid && finalPath == "SPEED");
   logV471WouldBlockLowNoTrade = V452BoolText(blocksLowNoTrade);
   logV471WouldBlockLowUnresolved = V452BoolText(blocksLowUnresolved);
   logV471WouldBlockHigh = V452BoolText(blocksHigh);
   logV471WouldBlockMid = V452BoolText(blocksMid);
   logV471WouldBlockSpeed = V452BoolText(blocksSpeed);

   if(!trackedAliveAt250ms[idx])
      AppendShadowSignal(notes, "DEAD_BEFORE_250MS");
   else if(trackedSampleMsAt250ms[idx] > 350)
      AppendShadowSignal(notes, "250MS_SAMPLE_DELAYED");
   if(!trackedAliveAt500ms[idx])
      AppendShadowSignal(notes, "DEAD_BEFORE_500MS");
   else if(trackedSampleMsAt500ms[idx] > 650)
      AppendShadowSignal(notes, "500MS_SAMPLE_DELAYED");
   if(!trackedAliveAt1s[idx])
      AppendShadowSignal(notes, "DEAD_BEFORE_1S");
   if(trackedTimeToFirstProfitMs[idx] <= 0)
      AppendShadowSignal(notes, "NO_FAVORABLE_TICK_BY_CLOSE");
   else
      AppendShadowSignal(notes, "FAVORABLE_TICK_SEEN");
   if(StringLen(trackedV471TickPath[idx]) <= 0)
      AppendShadowSignal(notes, "NO_TICK_PATH");
   if(logV45PreEntryHighShadowBucket == "HIGH" && logV461LowMicroClass == "LOW_NO_TRADE")
      AppendShadowSignal(notes, "PREENTRY_HIGH_ON_LOW_NO_TRADE");
   if(firstAvoid && heldMs > 0 && firstAvoidMs > heldMs)
      AppendShadowSignal(notes, "AFTER_ACTUAL_CLOSE");
   logV471CoverageNote = notes;
}

//+------------------------------------------------------------------+
void BuildV47DecisionFrontierTelemetry(const int idx,
                                       const bool isFOLM,
                                       const string eventTag,
                                       const double finalFav,
                                       const long heldMs,
                                       const string labels,
                                       const string qualityBucket)
{
   ClearV47DecisionFrontierLog();

   if(!UseV47DecisionFrontierTelemetry)
      return;

   string finalPath = V452FinalPathName(eventTag, finalFav);
   bool validIdx = (idx >= 0 && idx < ArraySize(trackedTickets));
   bool bucketPresent = (isFOLM && StringLen(qualityBucket) > 0);

   logV47BucketPresent = V452BoolText(bucketPresent);
   if(!isFOLM)
      logV47BucketNullReason = "NOT_FOLM";
   else if(!validIdx)
      logV47BucketNullReason = "NO_TRACKED_TICKET";
   else if(StringLen(qualityBucket) <= 0)
      logV47BucketNullReason = "NO_FOLM_QUALITY_BUCKET";

   logV47BucketAuditCloseReason = eventTag;
   logV47BucketAuditRoute = V452EntryRouteName(labels);
   logV47BucketAuditSession = logSessionBucket;
   logV47BucketAuditSpread = logSpreadRegime;
   logV47BucketAuditFinalPath = finalPath;
   logV47PreEntryShadowScore = logV45PreEntryHighShadowScore;
   logV47PreEntryShadowBucket = logV45PreEntryHighShadowBucket;
   logV47PreEntryShadowSignals = logV45PreEntryHighSignals;

   if(!isFOLM || !validIdx)
      return;

   bool valid500 = ValidTelemetrySnapshot(trackedFavAt500ms[idx]);
   bool valid1 = ValidTelemetrySnapshot(trackedFavAt1s[idx]);
   bool valid2 = ValidTelemetrySnapshot(trackedFavAt2s[idx]);
   bool valid3 = ValidTelemetrySnapshot(trackedFavAt3s[idx]);
   bool preEntryLow = (logV45PreEntryHighShadowBucket == "LOW");

   double maxFav1To2 = -ROUTER_BIG_VALUE;
   if(valid1)
      maxFav1To2 = trackedFavAt1s[idx];
   if(valid2 && trackedFavAt2s[idx] > maxFav1To2)
      maxFav1To2 = trackedFavAt2s[idx];

   double maxFav1To3 = V452MaxFav1To3(trackedFavAt1s[idx],
                                      trackedFavAt2s[idx],
                                      trackedFavAt3s[idx]);

   bool entryAvoid = (V47StageEnabled(0) && preEntryLow);
   bool avoid500 = (V47StageEnabled(500) &&
                    valid500 &&
                    trackedFavAt500ms[idx] <= V47LowNoTradeFavCeilingPoints &&
                    (trackedFirst500msMaxAdverseJumpPts[idx] >= V47EarlyAdverseJumpPoints ||
                     preEntryLow));
   bool avoid1 = (V47StageEnabled(1000) &&
                  valid1 &&
                  trackedFavAt1s[idx] <= V47LowNoTradeFavCeilingPoints &&
                  (trackedFirst1sMaxAdverseJumpPts[idx] >= V47EarlyAdverseJumpPoints ||
                   !V47FirstProfitBy(idx, 1000) ||
                   preEntryLow));
   bool avoid2 = (V47StageEnabled(2000) &&
                  valid1 &&
                  valid2 &&
                  maxFav1To2 <= V47LowNoTradeMaxFav1To3Points &&
                  (trackedFirst2sMaxAdverseJumpPts[idx] >= V47EarlyAdverseJumpPoints ||
                   !V47FirstProfitBy(idx, 2000)));
   bool avoid3 = (V47StageEnabled(3000) &&
                  valid1 &&
                  valid2 &&
                  valid3 &&
                  maxFav1To3 > -ROUTER_BIG_VALUE * 0.5 &&
                  maxFav1To3 <= V47LowNoTradeMaxFav1To3Points &&
                  (!V47FirstProfitBy(idx, 3000) ||
                   trackedFirst2sMaxAdverseJumpPts[idx] >= V47EarlyAdverseJumpPoints));

   logV47EntryAvoidShadow = V452BoolText(entryAvoid);
   logV47500msAvoidShadow = (valid500 && V47StageEnabled(500) ? V452BoolText(avoid500) : "");
   logV471sAvoidShadow = (valid1 && V47StageEnabled(1000) ? V452BoolText(avoid1) : "");
   logV472sAvoidShadow = (valid1 && valid2 && V47StageEnabled(2000) ? V452BoolText(avoid2) : "");
   logV473sAvoidShadow = (valid1 && valid2 && valid3 && V47StageEnabled(3000) ? V452BoolText(avoid3) : "");

   bool firstAvoid = false;
   double firstAvoidFav = 0.0;
   string avoidReason = "";

   if(entryAvoid)
   {
      firstAvoid = true;
      firstAvoidFav = 0.0;
      logV47FirstAvoidTimeMs = "0";
      logV47FirstAvoidStage = "ENTRY";
      AppendShadowSignal(avoidReason, "PRE_ENTRY_HIGH_SHADOW_LOW");
   }
   if(!firstAvoid && avoid500)
   {
      firstAvoid = true;
      firstAvoidFav = trackedFavAt500ms[idx];
      logV47FirstAvoidTimeMs = "500";
      logV47FirstAvoidStage = "500MS";
      AppendShadowSignal(avoidReason, "FAV_500MS_NON_POSITIVE");
      if(trackedFirst500msMaxAdverseJumpPts[idx] >= V47EarlyAdverseJumpPoints)
         AppendShadowSignal(avoidReason, "ADVERSE_500MS_GE_THRESHOLD");
      if(preEntryLow)
         AppendShadowSignal(avoidReason, "PRE_ENTRY_LOW");
   }
   if(!firstAvoid && avoid1)
   {
      firstAvoid = true;
      firstAvoidFav = trackedFavAt1s[idx];
      logV47FirstAvoidTimeMs = "1000";
      logV47FirstAvoidStage = "1S";
      AppendShadowSignal(avoidReason, "FAV_1S_NON_POSITIVE");
      if(trackedFirst1sMaxAdverseJumpPts[idx] >= V47EarlyAdverseJumpPoints)
         AppendShadowSignal(avoidReason, "ADVERSE_1S_GE_THRESHOLD");
      if(!V47FirstProfitBy(idx, 1000))
         AppendShadowSignal(avoidReason, "NO_FIRST_PROFIT_BY_1S");
   }
   if(!firstAvoid && avoid2)
   {
      firstAvoid = true;
      firstAvoidFav = trackedFavAt2s[idx];
      logV47FirstAvoidTimeMs = "2000";
      logV47FirstAvoidStage = "2S";
      AppendShadowSignal(avoidReason, "MAX_FAV_1TO2_NON_POSITIVE");
      if(trackedFirst2sMaxAdverseJumpPts[idx] >= V47EarlyAdverseJumpPoints)
         AppendShadowSignal(avoidReason, "ADVERSE_2S_GE_THRESHOLD");
      if(!V47FirstProfitBy(idx, 2000))
         AppendShadowSignal(avoidReason, "NO_FIRST_PROFIT_BY_2S");
   }
   if(!firstAvoid && avoid3)
   {
      firstAvoid = true;
      firstAvoidFav = trackedFavAt3s[idx];
      logV47FirstAvoidTimeMs = "3000";
      logV47FirstAvoidStage = "3S";
      AppendShadowSignal(avoidReason, "MAX_FAV_1TO3_NON_POSITIVE");
      if(!V47FirstProfitBy(idx, 3000))
         AppendShadowSignal(avoidReason, "NO_FIRST_PROFIT_BY_3S");
   }

   logV47AvoidReason = avoidReason;
   if(firstAvoid)
      logV47AvoidReplayDelta = DoubleToString(firstAvoidFav - finalFav, 1);

   bool blocksLowNoTrade = (firstAvoid && logV461LowMicroClass == "LOW_NO_TRADE");
   bool blocksLowUnresolved = (firstAvoid &&
                               (logV461LowMicroClass == "LOW_UNRESOLVED" ||
                                logV461LowMicroClass == "LOW_FALSE_ALARM"));
   bool blocksHigh = (firstAvoid && qualityBucket == "HIGH");
   bool blocksMid = (firstAvoid && qualityBucket == "MID");
   bool blocksSpeed = (firstAvoid && finalPath == "SPEED");

   logV47WouldBlockLowNoTrade = V452BoolText(blocksLowNoTrade);
   logV47WouldBlockLowUnresolved = V452BoolText(blocksLowUnresolved);
   logV47WouldBlockHigh = V452BoolText(blocksHigh);
   logV47WouldBlockMid = V452BoolText(blocksMid);
   logV47WouldBlockSpeed = V452BoolText(blocksSpeed);
   logV47TimeToFirstFavorableTickMs = (trackedTimeToFirstProfitMs[idx] > 0 ? (string)trackedTimeToFirstProfitMs[idx] : "");
   logV47First500msAdverseJump = DoubleToString(trackedFirst500msMaxAdverseJumpPts[idx], 1);
   logV47First1sAdverseJump = DoubleToString(trackedFirst1sMaxAdverseJumpPts[idx], 1);
   logV47First2sAdverseJump = DoubleToString(trackedFirst2sMaxAdverseJumpPts[idx], 1);

   string notes = "";
   if(!bucketPresent)
      AppendShadowSignal(notes, logV47BucketNullReason);
   if(blocksLowNoTrade)
      AppendShadowSignal(notes, "CAPTURES_LOW_NO_TRADE");
   if(blocksLowUnresolved)
      AppendShadowSignal(notes, "PROTECT_LOW_UNRESOLVED");
   if(blocksHigh || blocksMid)
      AppendShadowSignal(notes, "PROTECT_HIGH_MID");
   if(blocksSpeed)
      AppendShadowSignal(notes, "PROTECT_SPEED");
   if(firstAvoid && heldMs > 0 && StringToInteger(logV47FirstAvoidTimeMs) > heldMs)
      AppendShadowSignal(notes, "AFTER_ACTUAL_CLOSE");
   logV47FrontierNotes = notes;
}

//+------------------------------------------------------------------+
string V452EntryRouteName(const string labels)
{
   if(StringFind(labels, ":BM:") >= 0) return "BM";
   if(StringFind(labels, ":SM:") >= 0) return "SM";
   if(StringFind(labels, ":BS:") >= 0) return "BS";
   if(StringFind(labels, ":SS:") >= 0) return "SS";
   if(StringFind(labels, ":BL:") >= 0) return "BL";
   if(StringFind(labels, ":SL:") >= 0) return "SL";
   return "OTHER";
}

//+------------------------------------------------------------------+
string V452FinalPathName(const string eventTag, const double finalFav)
{
   if(StringFind(eventTag, "SPEED_PROFIT_EXIT") >= 0)
      return "SPEED";
   if(finalFav < 0.0)
      return "LOSS";
   if(finalFav > 0.0)
      return "POSITIVE_NON_SPEED";
   return "FLAT";
}

//+------------------------------------------------------------------+
double V452MaxFav1To3(const double fav1s, const double fav2s, const double fav3s)
{
   double maxFav = -ROUTER_BIG_VALUE;
   if(ValidTelemetrySnapshot(fav1s) && fav1s > maxFav)
      maxFav = fav1s;
   if(ValidTelemetrySnapshot(fav2s) && fav2s > maxFav)
      maxFav = fav2s;
   if(ValidTelemetrySnapshot(fav3s) && fav3s > maxFav)
      maxFav = fav3s;
   return maxFav;
}

//+------------------------------------------------------------------+
string V452BoolText(const bool value)
{
   return (value ? "true" : "false");
}

//+------------------------------------------------------------------+
string V452PressureActionableName(const string labels,
                                  const string sourceTiming,
                                  const long sourceMs)
{
   if(StringLen(sourceTiming) > 0)
      return (sourceMs <= 3000 ? "pre3s_source" : "post3s_source");
   if(V451LabelsHaveFlowOppPressure(labels))
      return "close_label_only";
   return "none";
}

//+------------------------------------------------------------------+
void BuildV452LowWinnerMicroscopeTelemetry(const bool isFOLM,
                                           const string eventTag,
                                           const double finalFav,
                                           const string labels,
                                           const string qualityBucket,
                                           const double fav1s,
                                           const double fav2s,
                                           const double fav3s,
                                           const double first10sMfe,
                                           const double first1sAdverseJump,
                                           const double first2sAdverseJump,
                                           const string pressureSourceTiming,
                                           const long pressureSourceMs)
{
   ClearV452LowWinnerMicroscopeLog();

   if(!UseV452LowWinnerMicroscope || !isFOLM)
      return;

   bool isLow = (qualityBucket == "LOW");
   logV452LowMicroscopeActive = V452BoolText(isLow);
   if(!isLow)
      return;

   string finalPath = V452FinalPathName(eventTag, finalFav);
   string route = V452EntryRouteName(labels);
   bool validFav1 = ValidTelemetrySnapshot(fav1s);
   bool validFav2 = ValidTelemetrySnapshot(fav2s);
   bool validFav3 = ValidTelemetrySnapshot(fav3s);
   double maxFav = V452MaxFav1To3(fav1s, fav2s, fav3s);
   bool hasMaxFav = (maxFav > -ROUTER_BIG_VALUE * 0.5);
   bool had1sJump = (V451LOWJFirst1sAdversePoints > 0.0 &&
                     first1sAdverseJump >= V451LOWJFirst1sAdversePoints);
   bool had2sJump = (V451LOWJFirst2sAdversePoints > 0.0 &&
                     first2sAdverseJump >= V451LOWJFirst2sAdversePoints);
   bool hadEarlyJump = (had1sJump || had2sJump);
   bool recoveredBy3s = (validFav3 && fav3s > 0.0);
   bool recoveredToSpeed = (hadEarlyJump && finalPath == "SPEED");
   bool pressureBefore3s = (StringLen(pressureSourceTiming) > 0 && pressureSourceMs <= 3000);
   bool deadStrict = (finalPath == "LOSS" &&
                      hasMaxFav &&
                      maxFav <= 0.0 &&
                      first10sMfe <= V452LowDeadMfeCeilingPoints);
   bool killRisk = (finalPath == "SPEED" ||
                    recoveredBy3s ||
                    first10sMfe >= V452LowEscapeMfeFloorPoints);

   string recoveryProfile = "";
   if(finalPath == "SPEED")
   {
      if(hadEarlyJump && recoveredBy3s)
         recoveryProfile = "LOW_SPEED_SNAPBACK";
      else if(first10sMfe >= V452LowEscapeMfeFloorPoints)
         recoveryProfile = "LOW_SPEED_LATE_EXPANSION";
      else
         recoveryProfile = "LOW_SPEED_OTHER";
   }
   else if(finalPath == "LOSS")
   {
      if(deadStrict)
         recoveryProfile = "LOW_DEAD_NO_RECOVERY";
      else if(hadEarlyJump && !recoveredBy3s && first10sMfe <= V452LowDeadMfeCeilingPoints)
         recoveryProfile = "LOW_JUMP_DEAD";
      else if(first10sMfe >= V452LowEscapeMfeFloorPoints)
         recoveryProfile = "LOW_EXPANDED_THEN_FAILED";
      else if(pressureBefore3s || V451LabelsHaveFlowOppPressure(labels))
         recoveryProfile = "LOW_PRESSURE_LOSS";
      else
         recoveryProfile = "LOW_WEAK_LOSS";
   }
   else
      recoveryProfile = "LOW_OTHER";

   string escapeReason = "";
   if(finalPath == "SPEED" || killRisk)
   {
      if(route == "BM")
         AppendShadowSignal(escapeReason, "BM_ROUTE");
      if(route == "SM")
         AppendShadowSignal(escapeReason, "SM_ROUTE");
      if(recoveredBy3s)
         AppendShadowSignal(escapeReason, "FAV3_RECOVERY");
      if(first10sMfe >= V452LowEscapeMfeFloorPoints)
         AppendShadowSignal(escapeReason, "MFE10_EXPANSION");
      if(hadEarlyJump && recoveredToSpeed)
         AppendShadowSignal(escapeReason, "JUMP_RECOVERED_TO_SPEED");
      if(!pressureBefore3s)
         AppendShadowSignal(escapeReason, "NO_PRE3S_PRESSURE");
   }
   if(StringLen(escapeReason) <= 0)
      escapeReason = "NONE";

   logV452LowFinalPath = finalPath;
   logV452LowEntryRoute = route;
   logV452LowRecoveryProfile = recoveryProfile;
   logV452LowFav1ToFav3Delta = (validFav1 && validFav3 ? DoubleToString(fav3s - fav1s, 1) : "");
   logV452LowFav2ToFav3Delta = (validFav2 && validFav3 ? DoubleToString(fav3s - fav2s, 1) : "");
   logV452LowMaxFav1To3 = (hasMaxFav ? DoubleToString(maxFav, 1) : "");
   logV452LowHad1sAdverseJump = V452BoolText(had1sJump);
   logV452LowHad2sAdverseJump = V452BoolText(had2sJump);
   logV452LowJumpRecoveredBy3s = (hadEarlyJump ? V452BoolText(recoveredBy3s) : "");
   logV452LowJumpRecoveredToSpeed = (hadEarlyJump ? V452BoolText(recoveredToSpeed) : "");
   logV452LowPressureActionable = V452PressureActionableName(labels, pressureSourceTiming, pressureSourceMs);
   logV452LowPressureBefore3s = V452BoolText(pressureBefore3s);
   logV452LowEscapeReason = escapeReason;
   logV452LowKillRiskFlag = V452BoolText(killRisk);
   logV452LowDeadStrict = V452BoolText(deadStrict);
}

//+------------------------------------------------------------------+
string CsvEscape(string value)
{
   StringReplace(value, "\"", "\"\"");
   if(StringFind(value, ",") >= 0 ||
      StringFind(value, "\"") >= 0 ||
      StringFind(value, "\r") >= 0 ||
      StringFind(value, "\n") >= 0)
      return "\"" + value + "\"";
   return value;
}

//+------------------------------------------------------------------+
void CsvAdd(string &row, const string value)
{
   if(StringLen(row) > 0)
      row += ",";
   row += CsvEscape(value);
}

//+------------------------------------------------------------------+
void CsvWriteLine(const int handle, const string row)
{
   FileWriteString(handle, row + "\r\n");
}

//+------------------------------------------------------------------+
void SarOrderFlowDecisionWriteHeader()
{
   int h = FileOpen(SAR_ORDER_FLOW_DECISION_V2_FILE,
                    FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI |
                    FILE_SHARE_READ | FILE_SHARE_WRITE, ",");
   if(h == INVALID_HANDLE)
   {
      if(!orderFlowDecisionFileErrorLogged)
      {
         Print("SAR_ORDER_FLOW_DECISION_V2_FILE_OPEN_FAILED error=",
               GetLastError());
         orderFlowDecisionFileErrorLogged = true;
      }
      return;
   }
   if(FileSize(h) == 0)
   {
      string header = "";
      CsvAdd(header, "schema_version");
      CsvAdd(header, "time_msc");
      CsvAdd(header, "symbol");
      CsvAdd(header, "magic");
      CsvAdd(header, "event");
      CsvAdd(header, "action");
      CsvAdd(header, "side");
      CsvAdd(header, "flow_gv_prefix");
      CsvAdd(header, "max_flow_age_ms");
      CsvAdd(header, "master_vwap_value");
      CsvAdd(header, "master_vwap_valid");
      CsvAdd(header, "master_vwap_age_ms");
      CsvAdd(header, "master_vwap_contributors");
      CsvAdd(header, "broker_mid");
      CsvAdd(header, "master_vwap_degraded");
      SARCaptureAppendHeader(header);
      CsvWriteLine(h, header);
   }
   FileClose(h);
}

//+------------------------------------------------------------------+
bool IsSarOrderFlowDecisionEvent(const string eventName,
                                 const RouterAction action)
{
   if(action != ActSkip)
      return true;
   return (StringFind(eventName, "SKIP") == 0);
}

//+------------------------------------------------------------------+
void SarOrderFlowDecisionLog(const string eventName,
                             const RouterAction action,
                             const DirectionState &state)
{
   if(!IsSarOrderFlowDecisionEvent(eventName, action))
      return;

   MqlTick t;
   ZeroMemory(t);
   t.bid=state.capture.quote_bid;t.ask=state.capture.quote_ask;t.time_msc=state.capture.quote_time_msc;
   double brokerMid=(t.bid+t.ask)*0.5;
   MasterVwapTelemetry masterVwap=state.capturedMasterVwap;

   int h = FileOpen(SAR_ORDER_FLOW_DECISION_V2_FILE,
                    FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI |
                    FILE_SHARE_READ | FILE_SHARE_WRITE, ",");
   if(h == INVALID_HANDLE)
   {
      if(!orderFlowDecisionFileErrorLogged)
      {
         Print("SAR_ORDER_FLOW_DECISION_V2_FILE_OPEN_FAILED error=",
               GetLastError());
         orderFlowDecisionFileErrorLogged = true;
      }
      return;
   }
   if(FileSize(h) == 0)
   {
      FileClose(h);
      SarOrderFlowDecisionWriteHeader();
      h = FileOpen(SAR_ORDER_FLOW_DECISION_V2_FILE,
                   FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI |
                   FILE_SHARE_READ | FILE_SHARE_WRITE, ",");
      if(h == INVALID_HANDLE)
         return;
   }

   int side = ActionSide(action);
   if(side == 0)
      side = WinnerSide(state);

   FileSeek(h, 0, SEEK_END);
   string row = "";
   CsvAdd(row, "sar.orderflow.decision.v2");
   CsvAdd(row, (string)GetTickMs());
   CsvAdd(row, _Symbol);
   CsvAdd(row, (string)MagicNumber);
   CsvAdd(row, eventName);
   CsvAdd(row, ActionName(action));
   CsvAdd(row, side > 0 ? "BUY" : (side < 0 ? "SELL" : ""));
   CsvAdd(row, FlowGVPrefix);
   CsvAdd(row, (string)MaxFlowAgeMs);
   CsvAdd(row, masterVwap.valid ? DoubleToString(masterVwap.value,
                                                 _Digits) : "");
   CsvAdd(row, masterVwap.valid ? "true" : "false");
   CsvAdd(row, masterVwap.heartbeatAvailable ? (string)masterVwap.ageMs : "");
   CsvAdd(row, masterVwap.valid ? (string)masterVwap.contributors : "");
   CsvAdd(row, masterVwap.brokerMid > 0.0 ? DoubleToString(masterVwap.brokerMid,
                                                           _Digits) : "");
   CsvAdd(row, masterVwap.degraded ? "true" : "false");
   SARCaptureAppend(row,state.capture);
   CsvWriteLine(h, row);
   FileClose(h);
}

//+------------------------------------------------------------------+
void AIDecisionAttemptWriteHeader()
{
   int h = FileOpen(THEORY_AI_DECISION_ATTEMPT_V1_FILE,
                    FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      Print("AI decision-attempt ledger open failed: ",
            THEORY_AI_DECISION_ATTEMPT_V1_FILE);
      return;
   }
   if(FileSize(h) == 0)
   {
      string header = "";
      CsvAdd(header, "schema_version");
      CsvAdd(header, "recorded_time");
      CsvAdd(header, "recorded_time_msc");
      CsvAdd(header, "account");
      CsvAdd(header, "magic");
      CsvAdd(header, "symbol");
      CsvAdd(header, "decision_identity");
      CsvAdd(header, "action");
      CsvAdd(header, "side");
      CsvAdd(header, "decision_time");
      CsvAdd(header, "decision_time_msc");
      CsvAdd(header, "context_valid");
      CsvAdd(header, "session_bucket");
      CsvAdd(header, "spread_points");
      CsvAdd(header, "velocity_1s_with_trade");
      CsvAdd(header, "velocity_3s_with_trade");
      CsvAdd(header, "velocity_5s_with_trade");
      CsvAdd(header, "velocity_1s_minus_3s_with_trade");
      CsvAdd(header, "velocity_3s_minus_5s_with_trade");
      CsvAdd(header, "force_imbalance_with_trade");
      CsvAdd(header, "near_imbalance_with_trade");
      CsvAdd(header, "book_imbalance_with_trade");
      CsvAdd(header, "body_direction_with_trade");
      CsvAdd(header, "micro_direction_with_trade");
      CsvAdd(header, "flow_direction_with_trade");
      CsvAdd(header, "flow_fresh");
      CsvAdd(header, "opposite_pressure");
      CsvAdd(header, "continuation");
      CsvAdd(header, "exhaustion");
      CsvAdd(header, "retest_held");
      CsvAdd(header, "retest_failed");
      CsvAdd(header, "own_direction_score");
      CsvAdd(header, "opposite_direction_score");
      CsvAdd(header, "direction_score_edge");
      CsvAdd(header, "preentry_high_shadow_score");
      CsvAdd(header, "preentry_high_shadow_bucket");
      CsvAdd(header, "preentry_high_shadow_would_allow");
      CsvAdd(header, "preentry_high_shadow_would_block");
      CsvAdd(header, "preentry_high_shadow_signals");
      CsvAdd(header, "preentry_tape_health");
      CsvAdd(header, "preentry_velocity_decay_with_trade");
      CsvAdd(header, "pre_speed_signal_age_ms");
      CsvAdd(header, "mode2_shadow_signal");
      CsvAdd(header, "mode2_block_reason");
      CsvAdd(header, "mode2_opposite_flags");
      CsvAdd(header, "mode2_velocity_1s_with_trade");
      CsvAdd(header, "mode2_weight_factor");
      CsvAdd(header, "lots");
      CsvAdd(header, "requested_entry");
      CsvAdd(header, "requested_sl");
      CsvAdd(header, "requested_tp");
      CsvAdd(header, "trading_enabled");
      CsvAdd(header, "order_attempted");
      CsvAdd(header, "trade_api_ok");
      CsvAdd(header, "order_accepted");
      CsvAdd(header, "request_ticket");
      CsvAdd(header, "retcode");
      CsvAdd(header, "retcode_description");
      CsvAdd(header, "causal_status");
      CsvAdd(header, "contract_hash");
      CsvAdd(header, "hard_gate_effective");
      CsvAdd(header, "risk_adjust_effective");
      CsvAdd(header, "active_behavior_changed");
      CsvAdd(header, "policy_note");
      CsvAdd(header, "position_ticket");
      CsvAdd(header, "magic_number");
      CsvAdd(header, "symbol");
      CsvAdd(header, "close_mechanism");
      CsvAdd(header, "close_price");
      CsvAdd(header, "close_server_time_msc");
      CsvAdd(header, "closing_deal_ticket");
      CsvAdd(header, "run_tag");
      SARCaptureAppendHeader(header);
      CsvWriteLine(h, header);
   }
   FileClose(h);
}

//+------------------------------------------------------------------+
bool AIDecisionAttemptAcceptedRetcode(const uint retcode)
{
   return (retcode == TRADE_RETCODE_PLACED ||
           retcode == TRADE_RETCODE_DONE ||
           retcode == TRADE_RETCODE_DONE_PARTIAL);
}

//+------------------------------------------------------------------+
void AIDecisionAttemptLog(
   const SARCaptureLatch &capture,
   const RouterAction action,
   const int side,
   const TheoryAIPreEntryJourneyContextV1 &context,
   const double preEntryScore,
   const string preEntryBucket,
   const string preEntryAllow,
   const string preEntryBlock,
   const string preEntrySignals,
   const string v471TapeHealth,
   const double v471VelocityDecay,
   const long v471PreSpeedSignalAgeMs,
   const string v48Mode2Signal,
   const string v48Mode2BlockReason,
   const int v48Mode2OppFlags,
   const double v48Mode2Velocity1s,
   const double v48Mode2WeightFactor,
   const double lots,
   const double requestedEntry,
   const double requestedSl,
   const double requestedTp,
   const bool tradingEnabled,
   const bool orderAttempted,
   const bool tradeApiOk,
   const ulong requestTicket,
   const uint retcode,
   const string retcodeDescription)
{
   if(action == ActSkip || side == 0)
      return;

   long recordedMs = GetTickMs();
   long decisionMs = context.decision_ms;
   bool orderAccepted = (orderAttempted &&
                         tradeApiOk &&
                         AIDecisionAttemptAcceptedRetcode(retcode));
   string decisionIdentity =
      (string)AccountInfoInteger(ACCOUNT_LOGIN) + ":" +
      (string)MagicNumber + ":" + _Symbol + ":" +
      (string)decisionMs + ":" + ActionName(action);

   int h = FileOpen(THEORY_AI_DECISION_ATTEMPT_V1_FILE,
                    FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      Print("AI decision-attempt row open failed: ",
            THEORY_AI_DECISION_ATTEMPT_V1_FILE);
      return;
   }
   FileSeek(h, 0, SEEK_END);
   string row = "";
   CsvAdd(row, THEORY_AI_DECISION_ATTEMPT_V1_SCHEMA);
   CsvAdd(row, TimeToString((datetime)(recordedMs / 1000),
                            TIME_DATE | TIME_SECONDS));
   CsvAdd(row, (string)recordedMs);
   CsvAdd(row, (string)AccountInfoInteger(ACCOUNT_LOGIN));
   CsvAdd(row, (string)MagicNumber);
   CsvAdd(row, _Symbol);
   CsvAdd(row, decisionIdentity);
   CsvAdd(row, ActionName(action));
   CsvAdd(row, (side > 0 ? "buy" : "sell"));
   CsvAdd(row, (decisionMs > 0
                ? TimeToString((datetime)(decisionMs / 1000),
                               TIME_DATE | TIME_SECONDS)
                : ""));
   CsvAdd(row, (decisionMs > 0 ? (string)decisionMs : ""));
   CsvAdd(row, (context.valid ? "true" : "false"));
   CsvAdd(row, (context.valid ? context.session_bucket : ""));
   CsvAdd(row, (context.valid ? DoubleToString(context.spread_points, 1) : ""));
   CsvAdd(row, (context.valid ? DoubleToString(context.velocity_1s_with_trade, 6) : ""));
   CsvAdd(row, (context.valid ? DoubleToString(context.velocity_3s_with_trade, 6) : ""));
   CsvAdd(row, (context.valid ? DoubleToString(context.velocity_5s_with_trade, 6) : ""));
   CsvAdd(row, (context.valid ? DoubleToString(context.velocity_1s_minus_3s_with_trade, 6) : ""));
   CsvAdd(row, (context.valid ? DoubleToString(context.velocity_3s_minus_5s_with_trade, 6) : ""));
   CsvAdd(row, (context.valid ? DoubleToString(context.force_imbalance_with_trade, 6) : ""));
   CsvAdd(row, (context.valid ? DoubleToString(context.near_imbalance_with_trade, 6) : ""));
   CsvAdd(row, (context.valid ? DoubleToString(context.book_imbalance_with_trade, 6) : ""));
   CsvAdd(row, (context.valid ? IntegerToString(context.body_direction_with_trade) : ""));
   CsvAdd(row, (context.valid ? IntegerToString(context.micro_direction_with_trade) : ""));
   CsvAdd(row, (context.valid ? IntegerToString(context.flow_direction_with_trade) : ""));
   CsvAdd(row, (context.valid ? (context.flow_fresh ? "true" : "false") : ""));
   CsvAdd(row, (context.valid ? (context.opposite_pressure ? "true" : "false") : ""));
   CsvAdd(row, (context.valid ? (context.continuation ? "true" : "false") : ""));
   CsvAdd(row, (context.valid ? (context.exhaustion ? "true" : "false") : ""));
   CsvAdd(row, (context.valid ? (context.retest_held ? "true" : "false") : ""));
   CsvAdd(row, (context.valid ? (context.retest_failed ? "true" : "false") : ""));
   CsvAdd(row, (context.valid ? DoubleToString(context.own_direction_score, 6) : ""));
   CsvAdd(row, (context.valid ? DoubleToString(context.opposite_direction_score, 6) : ""));
   CsvAdd(row, (context.valid ? DoubleToString(context.direction_score_edge, 6) : ""));
   CsvAdd(row, DoubleToString(preEntryScore, 6));
   CsvAdd(row, preEntryBucket);
   CsvAdd(row, preEntryAllow);
   CsvAdd(row, preEntryBlock);
   CsvAdd(row, preEntrySignals);
   CsvAdd(row, v471TapeHealth);
   CsvAdd(row, DoubleToString(v471VelocityDecay, 6));
   CsvAdd(row, (v471PreSpeedSignalAgeMs >= 0
                ? (string)v471PreSpeedSignalAgeMs
                : ""));
   CsvAdd(row, v48Mode2Signal);
   CsvAdd(row, v48Mode2BlockReason);
   CsvAdd(row, IntegerToString(v48Mode2OppFlags));
   CsvAdd(row, DoubleToString(v48Mode2Velocity1s, 6));
   CsvAdd(row, DoubleToString(v48Mode2WeightFactor, 6));
   CsvAdd(row, DoubleToString(lots, 2));
   CsvAdd(row, (requestedEntry > 0.0 ? DoubleToString(requestedEntry, _Digits) : ""));
   CsvAdd(row, (requestedSl > 0.0 ? DoubleToString(requestedSl, _Digits) : ""));
   CsvAdd(row, (requestedTp > 0.0 ? DoubleToString(requestedTp, _Digits) : ""));
   CsvAdd(row, (tradingEnabled ? "true" : "false"));
   CsvAdd(row, (orderAttempted ? "true" : "false"));
   CsvAdd(row, (tradeApiOk ? "true" : "false"));
   CsvAdd(row, (orderAccepted ? "true" : "false"));
   CsvAdd(row, (requestTicket > 0 ? (string)requestTicket : ""));
   CsvAdd(row, (orderAttempted ? (string)retcode : ""));
   CsvAdd(row, retcodeDescription);
   CsvAdd(row, "FEATURES_CAPTURED_BEFORE_TRADE_API_RESULT_RECORDED_AFTER");
   CsvAdd(row, THEORY_AI_DECISION_ATTEMPT_V1_CONTRACT_HASH);
   CsvAdd(row, "false");
   CsvAdd(row, "false");
   CsvAdd(row, "false");
   CsvAdd(row, "RESEARCH_ONLY_RAW_FEATURES_NO_SCORE_NO_GATE_NO_RISK_NO_ROUTE_NO_CLOSE");
   CsvAdd(row, "");
   CsvAdd(row, (string)MagicNumber);
   CsvAdd(row, _Symbol);
   CsvAdd(row, "");
   CsvAdd(row, "");
   CsvAdd(row, "");
   CsvAdd(row, "");
   CsvAdd(row, SAR_LIFECYCLE_RUN_TAG);
   SARCaptureAppend(row,capture);
   CsvWriteLine(h, row);
   FileClose(h);
}

//+------------------------------------------------------------------+
void AIShadowWriteHeader()
{
   int h = FileOpen(InpAIShadowLogFile, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      Print("AI shadow ledger open failed: ", InpAIShadowLogFile);
      return;
   }
   if(FileSize(h) == 0)
   {
      string header = "";
      CsvAdd(header, "schema_version");
      CsvAdd(header, "recorded_time");
      CsvAdd(header, "entry_time");
      CsvAdd(header, "entry_time_msc");
      CsvAdd(header, "account");
      CsvAdd(header, "magic");
      CsvAdd(header, "symbol");
      CsvAdd(header, "position_ticket");
      CsvAdd(header, "position_identifier");
      CsvAdd(header, "request_ticket");
      CsvAdd(header, "action");
      CsvAdd(header, "side");
      CsvAdd(header, "entry_second");
      CsvAdd(header, "entry_hour");
      CsvAdd(header, "entry_minute10");
      CsvAdd(header, "entry_dow_python");
      CsvAdd(header, "pending_age_seconds");
      CsvAdd(header, "age_bucket");
      CsvAdd(header, "prior_entry_gap_seconds");
      CsvAdd(header, "gap_bucket");
      CsvAdd(header, "ai_score");
      CsvAdd(header, "ai_score_band");
      CsvAdd(header, "ai_action_shadow");
      CsvAdd(header, "ai_reason");
      CsvAdd(header, "ai_risk_multiplier_shadow");
      CsvAdd(header, "causal_status");
      CsvAdd(header, "transfer_scope");
      CsvAdd(header, "model_hash");
      CsvAdd(header, "contract_hash");
      CsvAdd(header, "source_report_hash");
      CsvAdd(header, "hard_gate_input");
      CsvAdd(header, "risk_adjust_input");
      CsvAdd(header, "hard_gate_effective");
      CsvAdd(header, "risk_adjust_effective");
      CsvAdd(header, "active_behavior_changed");
      CsvAdd(header, "policy_note");
      CsvWriteLine(h, header);
   }
   FileClose(h);
}

//+------------------------------------------------------------------+
void AIShadowRestoreEntryClock()
{
   aiShadowCurrentEntrySecondMs = 0;
   aiShadowPriorEntrySecondMs = 0;
   datetime endTime = TimeCurrent();
   datetime startTime = endTime - 365 * 86400;
   if(!HistorySelect(startTime, endTime))
      return;

   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong dealTicket = HistoryDealGetTicket(i);
      if(dealTicket == 0)
         continue;
      if(HistoryDealGetString(dealTicket, DEAL_SYMBOL) != _Symbol ||
         HistoryDealGetInteger(dealTicket, DEAL_MAGIC) != MagicNumber)
         continue;
      ENUM_DEAL_ENTRY entryType = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
      if(entryType != DEAL_ENTRY_IN && entryType != DEAL_ENTRY_INOUT)
         continue;
      long entryMs = (long)HistoryDealGetInteger(dealTicket, DEAL_TIME_MSC);
      long entrySecondMs = (entryMs / 1000) * 1000;
      if(entrySecondMs <= 0)
         continue;
      if(entrySecondMs > aiShadowCurrentEntrySecondMs)
      {
         aiShadowPriorEntrySecondMs = aiShadowCurrentEntrySecondMs;
         aiShadowCurrentEntrySecondMs = entrySecondMs;
      }
      else if(entrySecondMs < aiShadowCurrentEntrySecondMs &&
              entrySecondMs > aiShadowPriorEntrySecondMs)
         aiShadowPriorEntrySecondMs = entrySecondMs;
   }
}

//+------------------------------------------------------------------+
double AIShadowStrictGapSecondsAndRegister(const long entrySecondMs, bool &known)
{
   known = false;
   double gapSeconds = 0.0;
   if(entrySecondMs <= 0)
      return gapSeconds;

   if(aiShadowCurrentEntrySecondMs > 0)
   {
      if(entrySecondMs > aiShadowCurrentEntrySecondMs)
      {
         gapSeconds = (double)(entrySecondMs - aiShadowCurrentEntrySecondMs) / 1000.0;
         known = (gapSeconds > 0.0);
      }
      else if(entrySecondMs == aiShadowCurrentEntrySecondMs &&
              aiShadowPriorEntrySecondMs > 0)
      {
         gapSeconds = (double)(entrySecondMs - aiShadowPriorEntrySecondMs) / 1000.0;
         known = (gapSeconds > 0.0);
      }
   }

   if(entrySecondMs > aiShadowCurrentEntrySecondMs)
   {
      aiShadowPriorEntrySecondMs = aiShadowCurrentEntrySecondMs;
      aiShadowCurrentEntrySecondMs = entrySecondMs;
   }
   return gapSeconds;
}

//+------------------------------------------------------------------+
long AIShadowOrderSetupMs(const ulong requestTicket, const long decisionMs)
{
   if(requestTicket > 0)
   {
      if(HistoryOrderSelect(requestTicket))
      {
         long setupMs = (long)HistoryOrderGetInteger(requestTicket, ORDER_TIME_SETUP_MSC);
         if(setupMs > 0)
            return setupMs;
      }
      if(OrderSelect(requestTicket))
      {
         long setupMs = (long)OrderGetInteger(ORDER_TIME_SETUP_MSC);
         if(setupMs > 0)
            return setupMs;
      }
   }
   return decisionMs;
}

//+------------------------------------------------------------------+
string AIShadowIdentityKey(const ulong positionIdentifier)
{
   return "TheoryAIShadowV1." +
          IntegerToString((int)AccountInfoInteger(ACCOUNT_LOGIN)) + "." +
          (string)positionIdentifier;
}

//+------------------------------------------------------------------+
void AIShadowLogPositionEntry(const ulong positionTicket,
                              const ulong positionIdentifier,
                              const ulong requestTicket,
                              const RouterAction action,
                              const int side,
                              const long fillEventMs,
                              const long placementDecisionMs,
                              const bool matchedPendingRequest)
{
   if(positionIdentifier == 0 || side == 0 || fillEventMs <= 0)
      return;

   string identityKey = AIShadowIdentityKey(positionIdentifier);
   if(GlobalVariableCheck(identityKey))
      return;

   long entrySecondMs = (fillEventMs / 1000) * 1000;
   datetime entryTime = (datetime)(entrySecondMs / 1000);
   bool pendingAction = IsPendingAction(action);
   long setupMs = AIShadowOrderSetupMs(requestTicket, placementDecisionMs);
   long setupSecondMs = (setupMs / 1000) * 1000;
   bool ageKnown = (pendingAction &&
                    matchedPendingRequest &&
                    setupSecondMs > 0 &&
                    entrySecondMs >= setupSecondMs);
   double ageSeconds = (ageKnown
                        ? (double)(entrySecondMs - setupSecondMs) / 1000.0
                        : 0.0);
   int ageBucket = TheoryAIShadowV1AgeBucket(ageSeconds, ageKnown);

   bool gapKnown = false;
   double gapSeconds = AIShadowStrictGapSecondsAndRegister(entrySecondMs, gapKnown);
   int gapBucket = TheoryAIShadowV1GapBucket(gapSeconds, gapKnown);
   TheoryAIShadowV1Result score = TheoryAIShadowV1Evaluate(entryTime,
                                                           side,
                                                           ageBucket,
                                                           gapBucket);

   string causalStatus = "CAUSAL_FILL_SCORE_AGE_UNKNOWN";
   if(pendingAction && ageKnown && setupMs != placementDecisionMs)
      causalStatus = "CAUSAL_FILL_SCORE_ORDER_SETUP_TO_FILL";
   else if(pendingAction && ageKnown)
      causalStatus = "CAUSAL_FILL_SCORE_DECISION_TO_FILL_PROXY";
   else if(!pendingAction)
      causalStatus = "CAUSAL_FILL_SCORE_MARKET_AGE_OUT_OF_DOMAIN";

   MqlDateTime parts;
   TimeToStruct(entryTime, parts);
   int pythonDow = (parts.day_of_week + 6) % 7;

   int h = FileOpen(InpAIShadowLogFile, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      Print("AI shadow score row open failed: ", InpAIShadowLogFile);
      return;
   }
   FileSeek(h, 0, SEEK_END);
   string row = "";
   CsvAdd(row, "theory.ai.shadow.entry.score.v1");
   CsvAdd(row, TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS));
   CsvAdd(row, TimeToString(entryTime, TIME_DATE | TIME_SECONDS));
   CsvAdd(row, (string)fillEventMs);
   CsvAdd(row, (string)AccountInfoInteger(ACCOUNT_LOGIN));
   CsvAdd(row, (string)MagicNumber);
   CsvAdd(row, _Symbol);
   CsvAdd(row, (string)positionTicket);
   CsvAdd(row, (string)positionIdentifier);
   CsvAdd(row, (string)requestTicket);
   CsvAdd(row, ActionName(action));
   CsvAdd(row, (side > 0 ? "buy" : "sell"));
   CsvAdd(row, IntegerToString(parts.sec));
   CsvAdd(row, IntegerToString(parts.hour));
   CsvAdd(row, IntegerToString(parts.min / 10));
   CsvAdd(row, IntegerToString(pythonDow));
   CsvAdd(row, (ageKnown ? DoubleToString(ageSeconds, 0) : ""));
   CsvAdd(row, IntegerToString(ageBucket));
   CsvAdd(row, (gapKnown ? DoubleToString(gapSeconds, 0) : ""));
   CsvAdd(row, IntegerToString(gapBucket));
   CsvAdd(row, (score.valid ? DoubleToString(score.score, 4) : ""));
   CsvAdd(row, score.score_band);
   CsvAdd(row, score.action_shadow);
   CsvAdd(row, score.reason);
   CsvAdd(row, DoubleToString(score.risk_multiplier_shadow, 2));
   CsvAdd(row, causalStatus);
   CsvAdd(row, THEORY_AI_SHADOW_V1_TRANSFER_SCOPE);
   CsvAdd(row, THEORY_AI_SHADOW_V1_MODEL_HASH);
   CsvAdd(row, THEORY_AI_SHADOW_V1_CONTRACT_HASH);
   CsvAdd(row, THEORY_AI_SHADOW_V1_SOURCE_HASH);
   CsvAdd(row, (InpAIHardGateEnabled ? "true" : "false"));
   CsvAdd(row, (InpAIRiskAdjustEnabled ? "true" : "false"));
   CsvAdd(row, "false");
   CsvAdd(row, "false");
   CsvAdd(row, "false");
   CsvAdd(row, "STAGE1_SHADOW_ONLY_EXTERNAL_TRANSFER_NO_BLOCK_NO_RISK_CHANGE");
   CsvAdd(row, (string)positionTicket);
   CsvAdd(row, (string)MagicNumber);
   CsvAdd(row, _Symbol);
   CsvAdd(row, "");
   CsvAdd(row, "");
   CsvAdd(row, "");
   CsvAdd(row, "");
   CsvAdd(row, SAR_LIFECYCLE_RUN_TAG);
   CsvWriteLine(h, row);
   FileFlush(h);
   FileClose(h);
   GlobalVariableSet(identityKey, (double)entrySecondMs);
}

//+------------------------------------------------------------------+
void AIPreEntryJourneyWriteHeader()
{
   int h = FileOpen(THEORY_AI_PREENTRY_JOURNEY_V1_FILE,
                    FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      Print("AI pre-entry journey ledger open failed: ",
            THEORY_AI_PREENTRY_JOURNEY_V1_FILE);
      return;
   }
   if(FileSize(h) == 0)
   {
      string header = "";
      CsvAdd(header, "schema_version");
      CsvAdd(header, "recorded_time");
      CsvAdd(header, "recorded_time_msc");
      CsvAdd(header, "account");
      CsvAdd(header, "magic");
      CsvAdd(header, "symbol");
      CsvAdd(header, "position_ticket");
      CsvAdd(header, "position_identifier");
      CsvAdd(header, "request_ticket");
      CsvAdd(header, "action");
      CsvAdd(header, "side");
      CsvAdd(header, "decision_time");
      CsvAdd(header, "decision_time_msc");
      CsvAdd(header, "fill_time_msc");
      CsvAdd(header, "decision_to_fill_ms");
      CsvAdd(header, "context_valid");
      CsvAdd(header, "identity_status");
      CsvAdd(header, "session_bucket");
      CsvAdd(header, "spread_points");
      CsvAdd(header, "velocity_1s_with_trade");
      CsvAdd(header, "velocity_3s_with_trade");
      CsvAdd(header, "velocity_5s_with_trade");
      CsvAdd(header, "velocity_1s_minus_3s_with_trade");
      CsvAdd(header, "velocity_3s_minus_5s_with_trade");
      CsvAdd(header, "force_imbalance_with_trade");
      CsvAdd(header, "near_imbalance_with_trade");
      CsvAdd(header, "book_imbalance_with_trade");
      CsvAdd(header, "body_direction_with_trade");
      CsvAdd(header, "micro_direction_with_trade");
      CsvAdd(header, "flow_direction_with_trade");
      CsvAdd(header, "flow_fresh");
      CsvAdd(header, "opposite_pressure");
      CsvAdd(header, "continuation");
      CsvAdd(header, "exhaustion");
      CsvAdd(header, "retest_held");
      CsvAdd(header, "retest_failed");
      CsvAdd(header, "own_direction_score");
      CsvAdd(header, "opposite_direction_score");
      CsvAdd(header, "direction_score_edge");
      CsvAdd(header, "preentry_high_shadow_score");
      CsvAdd(header, "preentry_high_shadow_bucket");
      CsvAdd(header, "preentry_high_shadow_signals");
      CsvAdd(header, "preentry_tape_health");
      CsvAdd(header, "preentry_velocity_decay_with_trade");
      CsvAdd(header, "pre_speed_signal_age_ms");
      CsvAdd(header, "mode2_shadow_signal");
      CsvAdd(header, "mode2_opposite_flags");
      CsvAdd(header, "mode2_velocity_1s_with_trade");
      CsvAdd(header, "mode2_weight_factor");
      CsvAdd(header, "contract_hash");
      CsvAdd(header, "hard_gate_effective");
      CsvAdd(header, "risk_adjust_effective");
      CsvAdd(header, "active_behavior_changed");
      CsvAdd(header, "policy_note");
      CsvAdd(header, "position_ticket");
      CsvAdd(header, "magic_number");
      CsvAdd(header, "symbol");
      CsvAdd(header, "close_mechanism");
      CsvAdd(header, "close_price");
      CsvAdd(header, "close_server_time_msc");
      CsvAdd(header, "closing_deal_ticket");
      CsvAdd(header, "run_tag");
      CsvWriteLine(h, header);
   }
   FileClose(h);
}

//+------------------------------------------------------------------+
string AIPreEntryJourneyIdentityKey(const ulong positionIdentifier)
{
   return "ThPreJv1." +
          (string)AccountInfoInteger(ACCOUNT_LOGIN) + "." +
          (string)positionIdentifier;
}

//+------------------------------------------------------------------+
void AIPreEntryJourneyLogPositionFill(
   const ulong positionTicket,
   const ulong positionIdentifier,
   const ulong requestTicket,
   const RouterAction action,
   const int side,
   const long fillEventMs,
   const long placementDecisionMs,
   const bool matchedPendingRequest,
   const TheoryAIPreEntryJourneyContextV1 &context,
   const double preEntryScore,
   const string preEntryBucket,
   const string preEntrySignals,
   const string v471TapeHealth,
   const double v471VelocityDecay,
   const long v471PreSpeedSignalAgeMs,
   const string v48Mode2Signal,
   const int v48Mode2OppFlags,
   const double v48Mode2Velocity1s,
   const double v48Mode2WeightFactor)
{
   if(positionIdentifier == 0 || side == 0 || fillEventMs <= 0)
      return;

   string identityKey = AIPreEntryJourneyIdentityKey(positionIdentifier);
   if(GlobalVariableCheck(identityKey))
      return;

   long decisionMs = (context.valid
                      ? context.decision_ms
                      : placementDecisionMs);
   bool timingValid = (decisionMs > 0 && fillEventMs >= decisionMs);
   string identityStatus = "NO_MATCHED_DECISION_CONTEXT";
   if(matchedPendingRequest && context.valid && timingValid)
      identityStatus = "MATCHED_REQUEST_DECISION_CONTEXT";
   else if(matchedPendingRequest && context.valid)
      identityStatus = "MATCHED_CONTEXT_INVALID_TIMING";
   else if(matchedPendingRequest)
      identityStatus = "MATCHED_REQUEST_CONTEXT_MISSING";

   long recordedMs = GetTickMs();
   int h = FileOpen(THEORY_AI_PREENTRY_JOURNEY_V1_FILE,
                    FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      Print("AI pre-entry journey row open failed: ",
            THEORY_AI_PREENTRY_JOURNEY_V1_FILE);
      return;
   }
   FileSeek(h, 0, SEEK_END);

   string row = "";
   CsvAdd(row, THEORY_AI_PREENTRY_JOURNEY_V1_SCHEMA);
   CsvAdd(row, TimeToString((datetime)(recordedMs / 1000),
                            TIME_DATE | TIME_SECONDS));
   CsvAdd(row, (string)recordedMs);
   CsvAdd(row, (string)AccountInfoInteger(ACCOUNT_LOGIN));
   CsvAdd(row, (string)MagicNumber);
   CsvAdd(row, _Symbol);
   CsvAdd(row, (string)positionTicket);
   CsvAdd(row, (string)positionIdentifier);
   CsvAdd(row, (string)requestTicket);
   CsvAdd(row, ActionName(action));
   CsvAdd(row, (side > 0 ? "buy" : "sell"));
   CsvAdd(row, (decisionMs > 0
                ? TimeToString((datetime)(decisionMs / 1000),
                               TIME_DATE | TIME_SECONDS)
                : ""));
   CsvAdd(row, (decisionMs > 0 ? (string)decisionMs : ""));
   CsvAdd(row, (string)fillEventMs);
   CsvAdd(row, (timingValid ? (string)(fillEventMs - decisionMs) : ""));
   CsvAdd(row, (context.valid ? "true" : "false"));
   CsvAdd(row, identityStatus);
   CsvAdd(row, (context.valid ? context.session_bucket : ""));
   CsvAdd(row, (context.valid
                ? DoubleToString(context.spread_points, 1)
                : ""));
   CsvAdd(row, (context.valid
                ? DoubleToString(context.velocity_1s_with_trade, 6)
                : ""));
   CsvAdd(row, (context.valid
                ? DoubleToString(context.velocity_3s_with_trade, 6)
                : ""));
   CsvAdd(row, (context.valid
                ? DoubleToString(context.velocity_5s_with_trade, 6)
                : ""));
   CsvAdd(row, (context.valid
                ? DoubleToString(context.velocity_1s_minus_3s_with_trade, 6)
                : ""));
   CsvAdd(row, (context.valid
                ? DoubleToString(context.velocity_3s_minus_5s_with_trade, 6)
                : ""));
   CsvAdd(row, (context.valid
                ? DoubleToString(context.force_imbalance_with_trade, 6)
                : ""));
   CsvAdd(row, (context.valid
                ? DoubleToString(context.near_imbalance_with_trade, 6)
                : ""));
   CsvAdd(row, (context.valid
                ? DoubleToString(context.book_imbalance_with_trade, 6)
                : ""));
   CsvAdd(row, (context.valid
                ? IntegerToString(context.body_direction_with_trade)
                : ""));
   CsvAdd(row, (context.valid
                ? IntegerToString(context.micro_direction_with_trade)
                : ""));
   CsvAdd(row, (context.valid
                ? IntegerToString(context.flow_direction_with_trade)
                : ""));
   CsvAdd(row, (context.valid ? (context.flow_fresh ? "true" : "false") : ""));
   CsvAdd(row, (context.valid
                ? (context.opposite_pressure ? "true" : "false")
                : ""));
   CsvAdd(row, (context.valid
                ? (context.continuation ? "true" : "false")
                : ""));
   CsvAdd(row, (context.valid
                ? (context.exhaustion ? "true" : "false")
                : ""));
   CsvAdd(row, (context.valid
                ? (context.retest_held ? "true" : "false")
                : ""));
   CsvAdd(row, (context.valid
                ? (context.retest_failed ? "true" : "false")
                : ""));
   CsvAdd(row, (context.valid
                ? DoubleToString(context.own_direction_score, 6)
                : ""));
   CsvAdd(row, (context.valid
                ? DoubleToString(context.opposite_direction_score, 6)
                : ""));
   CsvAdd(row, (context.valid
                ? DoubleToString(context.direction_score_edge, 6)
                : ""));
   CsvAdd(row, (matchedPendingRequest ? DoubleToString(preEntryScore, 6) : ""));
   CsvAdd(row, (matchedPendingRequest ? preEntryBucket : ""));
   CsvAdd(row, (matchedPendingRequest ? preEntrySignals : ""));
   CsvAdd(row, (matchedPendingRequest ? v471TapeHealth : ""));
   CsvAdd(row, (matchedPendingRequest
                ? DoubleToString(v471VelocityDecay, 6)
                : ""));
   CsvAdd(row, (matchedPendingRequest && v471PreSpeedSignalAgeMs >= 0
                ? (string)v471PreSpeedSignalAgeMs
                : ""));
   CsvAdd(row, (matchedPendingRequest ? v48Mode2Signal : ""));
   CsvAdd(row, (matchedPendingRequest
                ? IntegerToString(v48Mode2OppFlags)
                : ""));
   CsvAdd(row, (matchedPendingRequest
                ? DoubleToString(v48Mode2Velocity1s, 6)
                : ""));
   CsvAdd(row, (matchedPendingRequest
                ? DoubleToString(v48Mode2WeightFactor, 6)
                : ""));
   CsvAdd(row, THEORY_AI_PREENTRY_JOURNEY_V1_CONTRACT_HASH);
   CsvAdd(row, "false");
   CsvAdd(row, "false");
   CsvAdd(row, "false");
   CsvAdd(row, "RESEARCH_ONLY_NO_SCORE_NO_GATE_NO_RISK_NO_ROUTE_NO_CLOSE");
   CsvAdd(row, (string)positionTicket);
   CsvAdd(row, (string)MagicNumber);
   CsvAdd(row, _Symbol);
   CsvAdd(row, "");
   CsvAdd(row, "");
   CsvAdd(row, "");
   CsvAdd(row, "");
   CsvAdd(row, SAR_LIFECYCLE_RUN_TAG);
   CsvWriteLine(h, row);
   FileClose(h);
   GlobalVariableSet(identityKey, (double)recordedMs);
}

//+------------------------------------------------------------------+
void AIJourneyShadowWriteHeader()
{
   if(!InpAIJourneyShadowEnabled)
      return;

   int h = FileOpen(InpAIJourneyShadowLogFile,
                    FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      Print("AI journey shadow ledger open failed: ", InpAIJourneyShadowLogFile);
      return;
   }
   if(FileSize(h) == 0)
   {
      string header = "";
      CsvAdd(header, "schema_version");
      CsvAdd(header, "recorded_time");
      CsvAdd(header, "recorded_time_msc");
      CsvAdd(header, "account");
      CsvAdd(header, "magic");
      CsvAdd(header, "symbol");
      CsvAdd(header, "position_ticket");
      CsvAdd(header, "position_identifier");
      CsvAdd(header, "side");
      CsvAdd(header, "route");
      CsvAdd(header, "horizon_ms");
      CsvAdd(header, "sample_ms");
      CsvAdd(header, "sample_delay_ms");
      CsvAdd(header, "sample_valid");
      CsvAdd(header, "fav_points");
      CsvAdd(header, "prior_horizon_ms");
      CsvAdd(header, "prior_fav_points");
      CsvAdd(header, "fav_slope_points_per_second");
      CsvAdd(header, "tick_count");
      CsvAdd(header, "max_adverse_jump_points");
      CsvAdd(header, "journey_score");
      CsvAdd(header, "score_band");
      CsvAdd(header, "ai_action_shadow");
      CsvAdd(header, "ai_reason");
      CsvAdd(header, "all_window_auc");
      CsvAdd(header, "chronological_validation_auc");
      CsvAdd(header, "score_semantics");
      CsvAdd(header, "causal_status");
      CsvAdd(header, "model_hash");
      CsvAdd(header, "contract_hash");
      CsvAdd(header, "source_feature_hash");
      CsvAdd(header, "source_label_hash");
      CsvAdd(header, "source_report_hash");
      CsvAdd(header, "hard_gate_input");
      CsvAdd(header, "risk_adjust_input");
      CsvAdd(header, "hard_gate_effective");
      CsvAdd(header, "risk_adjust_effective");
      CsvAdd(header, "active_behavior_changed");
      CsvAdd(header, "policy_note");
      CsvAdd(header, "position_ticket");
      CsvAdd(header, "magic_number");
      CsvAdd(header, "symbol");
      CsvAdd(header, "close_mechanism");
      CsvAdd(header, "close_price");
      CsvAdd(header, "close_server_time_msc");
      CsvAdd(header, "closing_deal_ticket");
      CsvAdd(header, "run_tag");
      CsvWriteLine(h, header);
   }
   FileClose(h);
}

//+------------------------------------------------------------------+
string AIJourneyShadowIdentityKey(const ulong positionIdentifier,
                                  const int horizonMs)
{
   return "ThJv2." +
          (string)AccountInfoInteger(ACCOUNT_LOGIN) + "." +
          (string)positionIdentifier + "." +
          IntegerToString(horizonMs);
}

//+------------------------------------------------------------------+
int AIJourneyShadowValidMaxMs(const int horizonMs)
{
   if(horizonMs == 500) return 650;
   if(horizonMs == 750) return 900;
   if(horizonMs == 1000) return 1150;
   return 0;
}

//+------------------------------------------------------------------+
void AIJourneyShadowLogStage(const ulong positionTicket,
                             const ulong positionIdentifier,
                             const int side,
                             const string route,
                             const int horizonMs,
                             const long sampleMs,
                             const double fav,
                             const int priorHorizonMs,
                             const double priorFav,
                             const int tickCount,
                             const double maxAdverseJump,
                             const long eventTimeMs,
                             const bool trackerClockAligned)
{
   if(!InpAIJourneyShadowEnabled ||
      positionIdentifier == 0 ||
      side == 0 ||
      !TheoryJourneyShadowV2SupportedHorizon(horizonMs))
      return;

   string identityKey = AIJourneyShadowIdentityKey(positionIdentifier, horizonMs);
   if(GlobalVariableCheck(identityKey))
      return;

   int maxSampleMs = AIJourneyShadowValidMaxMs(horizonMs);
   bool sampleValid = (trackerClockAligned &&
                       sampleMs >= horizonMs &&
                       sampleMs <= maxSampleMs &&
                       MathIsValidNumber(fav) &&
                       MathAbs(fav) <= 1000000.0);

   TheoryJourneyShadowV2Result score;
   score.valid = false;
   score.horizon_ms = horizonMs;
   score.score = 0.0;
   score.score_band = "UNSCORABLE";
   score.action_shadow = "NO_RECOMMENDATION";
   score.reason = "INVALID_SAMPLE";
   if(sampleValid)
      score = TheoryJourneyShadowV2Evaluate(horizonMs,
                                            fav,
                                            priorHorizonMs,
                                            priorFav,
                                            tickCount,
                                            maxAdverseJump);

   string causalStatus = "CAUSAL_TICK_EVENT_SCORE";
   if(!trackerClockAligned)
      causalStatus = "TRACKER_CLOCK_MISMATCH_UNSCORABLE";
   else if(!sampleValid)
      causalStatus = "SAMPLE_DELAYED_UNSCORABLE";

   double slope = 0.0;
   bool slopeValid = (priorHorizonMs > 0 &&
                      priorHorizonMs < horizonMs &&
                      MathIsValidNumber(priorFav) &&
                      MathAbs(priorFav) <= 1000000.0);
   if(slopeValid)
   {
      double seconds = (double)(horizonMs - priorHorizonMs) / 1000.0;
      slope = (seconds > 0.0 ? (fav - priorFav) / seconds : 0.0);
   }

   int h = FileOpen(InpAIJourneyShadowLogFile,
                    FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      Print("AI journey shadow row open failed: ", InpAIJourneyShadowLogFile);
      return;
   }
   FileSeek(h, 0, SEEK_END);
   string row = "";
   CsvAdd(row, THEORY_JOURNEY_SHADOW_V2_SCHEMA);
   CsvAdd(row, TimeToString((datetime)(eventTimeMs / 1000),
                            TIME_DATE | TIME_SECONDS));
   CsvAdd(row, (string)eventTimeMs);
   CsvAdd(row, (string)AccountInfoInteger(ACCOUNT_LOGIN));
   CsvAdd(row, (string)MagicNumber);
   CsvAdd(row, _Symbol);
   CsvAdd(row, (string)positionTicket);
   CsvAdd(row, (string)positionIdentifier);
   CsvAdd(row, (side > 0 ? "buy" : "sell"));
   CsvAdd(row, route);
   CsvAdd(row, IntegerToString(horizonMs));
   CsvAdd(row, (string)sampleMs);
   CsvAdd(row, (string)(sampleMs - horizonMs));
   CsvAdd(row, (sampleValid ? "true" : "false"));
   CsvAdd(row, DoubleToString(fav, 1));
   CsvAdd(row, (slopeValid ? IntegerToString(priorHorizonMs) : ""));
   CsvAdd(row, (slopeValid ? DoubleToString(priorFav, 1) : ""));
   CsvAdd(row, (slopeValid ? DoubleToString(slope, 3) : ""));
   CsvAdd(row, IntegerToString(tickCount));
   CsvAdd(row, DoubleToString(maxAdverseJump, 1));
   CsvAdd(row, (score.valid ? DoubleToString(score.score, 4) : ""));
   CsvAdd(row, score.score_band);
   CsvAdd(row, score.action_shadow);
   CsvAdd(row, score.reason);
   CsvAdd(row, DoubleToString(TheoryJourneyShadowV2AllWindowAuc(horizonMs), 3));
   CsvAdd(row, DoubleToString(TheoryJourneyShadowV2ValidationAuc(horizonMs), 3));
   CsvAdd(row, "TRAINING_PERCENTILE_NOT_PROBABILITY");
   CsvAdd(row, causalStatus);
   CsvAdd(row, THEORY_JOURNEY_SHADOW_V2_MODEL_HASH);
   CsvAdd(row, THEORY_JOURNEY_SHADOW_V2_CONTRACT_HASH);
   CsvAdd(row, THEORY_JOURNEY_SHADOW_V2_SOURCE_FEATURE_HASH);
   CsvAdd(row, THEORY_JOURNEY_SHADOW_V2_SOURCE_LABEL_HASH);
   CsvAdd(row, THEORY_JOURNEY_SHADOW_V2_SOURCE_REPORT_HASH);
   CsvAdd(row, (InpAIHardGateEnabled ? "true" : "false"));
   CsvAdd(row, (InpAIRiskAdjustEnabled ? "true" : "false"));
   CsvAdd(row, "false");
   CsvAdd(row, "false");
   CsvAdd(row, "false");
   CsvAdd(row, THEORY_JOURNEY_SHADOW_V2_POLICY);
   CsvAdd(row, (string)positionTicket);
   CsvAdd(row, (string)MagicNumber);
   CsvAdd(row, _Symbol);
   CsvAdd(row, "");
   CsvAdd(row, "");
   CsvAdd(row, "");
   CsvAdd(row, "");
   CsvAdd(row, SAR_LIFECYCLE_RUN_TAG);
   CsvWriteLine(h, row);
   FileClose(h);
   GlobalVariableSet(identityKey, (double)eventTimeMs);
}

//+------------------------------------------------------------------+
void AIJourneyShadowMaybeLog(const int idx,
                             const ulong positionTicket,
                             const ulong positionIdentifier,
                             const int side,
                             const long positionEntryMs,
                             const long eventTimeMs)
{
   if(!InpAIJourneyShadowEnabled ||
      idx < 0 ||
      idx >= ArraySize(trackedTickets))
      return;

   bool trackerClockAligned = (positionEntryMs > 0 &&
                               MathAbs((double)(trackedEntryMs[idx] -
                                                       positionEntryMs)) <= 1000.0);
   string route = ActionName(ActionFromLabels(trackedLabels[idx]));

   if(trackedAliveAt500ms[idx])
   {
      bool priorValid = (trackedAliveAt250ms[idx] &&
                         trackedSampleMsAt250ms[idx] >= 250 &&
                         trackedSampleMsAt250ms[idx] <= 350);
      AIJourneyShadowLogStage(positionTicket,
                              positionIdentifier,
                              side,
                              route,
                              500,
                              trackedSampleMsAt500ms[idx],
                              trackedFavAt500ms[idx],
                              (priorValid ? 250 : 0),
                              (priorValid ? trackedFavAt250ms[idx] : 0.0),
                              trackedTicksAt500ms[idx],
                              trackedFirst500msMaxAdverseJumpPts[idx],
                              eventTimeMs,
                              trackerClockAligned);
   }
   if(trackedAliveAt750ms[idx])
   {
      bool priorValid = (trackedAliveAt500ms[idx] &&
                         trackedSampleMsAt500ms[idx] >= 500 &&
                         trackedSampleMsAt500ms[idx] <= 650);
      AIJourneyShadowLogStage(positionTicket,
                              positionIdentifier,
                              side,
                              route,
                              750,
                              trackedSampleMsAt750ms[idx],
                              trackedFavAt750ms[idx],
                              (priorValid ? 500 : 0),
                              (priorValid ? trackedFavAt500ms[idx] : 0.0),
                              trackedTicksAt750ms[idx],
                              trackedFirst750msMaxAdverseJumpPts[idx],
                              eventTimeMs,
                              trackerClockAligned);
   }
   if(trackedAliveAt1s[idx])
   {
      bool priorValid = (trackedAliveAt750ms[idx] &&
                         trackedSampleMsAt750ms[idx] >= 750 &&
                         trackedSampleMsAt750ms[idx] <= 900);
      AIJourneyShadowLogStage(positionTicket,
                              positionIdentifier,
                              side,
                              route,
                              1000,
                              trackedSampleMsAt1s[idx],
                              trackedFavAt1s[idx],
                              (priorValid ? 750 : 0),
                              (priorValid ? trackedFavAt750ms[idx] : 0.0),
                              trackedTicksAt1s[idx],
                              trackedFirst1sMaxAdverseJumpPts[idx],
                              eventTimeMs,
                              trackerClockAligned);
   }
}

//+------------------------------------------------------------------+
void AIT200ShadowWriteHeader()
{
   int h = FileOpen(THEORY_AI_T200_SHADOW_V2_FILE,
                    FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI |
                    FILE_SHARE_READ | FILE_SHARE_WRITE);
   if(h == INVALID_HANDLE)
   {
      Print("AI T200 rhythm shadow ledger open failed: ",
            THEORY_AI_T200_SHADOW_V2_FILE);
      return;
   }
   if(FileSize(h) == 0)
   {
      string header = "";
      CsvAdd(header, "schema_version");
      CsvAdd(header, "recorded_time_msc");
      CsvAdd(header, "account");
      CsvAdd(header, "magic");
      CsvAdd(header, "symbol");
      CsvAdd(header, "position_ticket");
      CsvAdd(header, "position_identifier");
      CsvAdd(header, "decision_identity");
      CsvAdd(header, "decision_time_msc");
      CsvAdd(header, "fill_time_msc");
      CsvAdd(header, "side");
      CsvAdd(header, "route");
      CsvAdd(header, "entry_price");
      CsvAdd(header, "initial_sl");
      CsvAdd(header, "event");
      CsvAdd(header, "event_time_msc");
      CsvAdd(header, "hold_ms");
      CsvAdd(header, "gross_exit_points");
      CsvAdd(header, "mfe_points");
      CsvAdd(header, "mae_points");
      CsvAdd(header, "armed");
      CsvAdd(header, "arm_time_msc");
      CsvAdd(header, "arm_rhythm");
      CsvAdd(header, "final_rhythm");
      CsvAdd(header, "active_stop");
      CsvAdd(header, "actual_position_open");
      CsvAdd(header, "sample_valid");
      CsvAdd(header, "causal_status");
      CsvAdd(header, "contract_hash");
      CsvAdd(header, "trading_authority");
      CsvAdd(header, "active_behavior_changed");
      CsvAdd(header, "position_ticket");
      CsvAdd(header, "magic_number");
      CsvAdd(header, "symbol");
      CsvAdd(header, "close_mechanism");
      CsvAdd(header, "close_price");
      CsvAdd(header, "close_server_time_msc");
      CsvAdd(header, "closing_deal_ticket");
      CsvAdd(header, "run_tag");
      CsvWriteLine(h, header);
   }
   FileClose(h);
}

//+------------------------------------------------------------------+
int AIT200ShadowPathIndex(const ulong positionIdentifier)
{
   for(int i = 0; i < ArraySize(aiT200ShadowPaths); i++)
      if(aiT200ShadowPaths[i].position_identifier == positionIdentifier)
         return i;
   return -1;
}

//+------------------------------------------------------------------+
void AIT200ShadowRemoveIndex(const int idx)
{
   int n = ArraySize(aiT200ShadowPaths);
   if(idx < 0 || idx >= n)
      return;
   for(int i = idx; i < n - 1; i++)
      aiT200ShadowPaths[i] = aiT200ShadowPaths[i + 1];
   ArrayResize(aiT200ShadowPaths, n - 1);
}

//+------------------------------------------------------------------+
bool ResolveCloseLifecycleFromPositionIdentifier(const ulong positionIdentifier,
                                                 string &mechanism,
                                                 double &closePrice,
                                                 long &closeTimeMsc,
                                                 ulong &closingDealTicket)
{
   mechanism = "";
   closePrice = 0.0;
   closeTimeMsc = 0;
   closingDealTicket = 0;
   if(positionIdentifier == 0 ||
      !HistorySelectByPosition(positionIdentifier))
      return false;

   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong dealTicket = HistoryDealGetTicket(i);
      if(dealTicket == 0)
         continue;
      if(HistoryDealGetString(dealTicket, DEAL_SYMBOL) != _Symbol ||
         HistoryDealGetInteger(dealTicket, DEAL_MAGIC) != MagicNumber)
         continue;

      ENUM_DEAL_ENTRY entryType =
         (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
      if(entryType != DEAL_ENTRY_OUT &&
         entryType != DEAL_ENTRY_OUT_BY &&
         entryType != DEAL_ENTRY_INOUT)
         continue;

      long dealTimeMsc = (long)HistoryDealGetInteger(dealTicket, DEAL_TIME_MSC);
      if(dealTimeMsc < closeTimeMsc)
         continue;

      double dealPrice = HistoryDealGetDouble(dealTicket, DEAL_PRICE);
      if(dealPrice <= 0.0)
         continue;

      closeTimeMsc = dealTimeMsc;
      closePrice = dealPrice;
      closingDealTicket = dealTicket;
      mechanism =
         CloseMechanismFromDealReason(HistoryDealGetInteger(dealTicket,
                                                            DEAL_REASON));
   }

   return (closingDealTicket > 0);
}

//+------------------------------------------------------------------+
bool AIT200ShadowLog(const TheoryAIT200ShadowV2Path &path,
                     const string eventName,
                     const long eventTimeMs,
                     const double grossPoints,
                     const bool sampleValid,
                     const string causalStatus)
{
   int h = FileOpen(THEORY_AI_T200_SHADOW_V2_FILE,
                    FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI |
                    FILE_SHARE_READ | FILE_SHARE_WRITE);
   if(h == INVALID_HANDLE)
   {
      Print("AI T200 rhythm shadow row open failed: ",
            THEORY_AI_T200_SHADOW_V2_FILE);
      return false;
   }
   FileSeek(h, 0, SEEK_END);
   long heldMs = eventTimeMs - path.fill_time_msc;
   if(heldMs < 0)
      heldMs = 0;
   bool actualPositionOpen = PositionSelectByTicket(path.position_ticket);
   string closeMechanism = "";
   double closePrice = 0.0;
   long closeTimeMsc = 0;
   ulong closingDealTicket = 0;
   if(!actualPositionOpen && eventName != "START")
      ResolveCloseLifecycleFromPositionIdentifier(path.position_identifier,
                                                  closeMechanism,
                                                  closePrice,
                                                  closeTimeMsc,
                                                  closingDealTicket);

   string row = "";
   CsvAdd(row, THEORY_AI_T200_SHADOW_V2_SCHEMA);
   CsvAdd(row, (string)GetTickMs());
   CsvAdd(row, (string)AccountInfoInteger(ACCOUNT_LOGIN));
   CsvAdd(row, (string)MagicNumber);
   CsvAdd(row, _Symbol);
   CsvAdd(row, (string)path.position_ticket);
   CsvAdd(row, (string)path.position_identifier);
   CsvAdd(row, path.decision_identity);
   CsvAdd(row, (string)path.decision_time_msc);
   CsvAdd(row, (string)path.fill_time_msc);
   CsvAdd(row, (path.side > 0 ? "BUY" : "SELL"));
   CsvAdd(row, path.route);
   CsvAdd(row, DoubleToString(path.entry_price, _Digits));
   CsvAdd(row, DoubleToString(path.initial_sl, _Digits));
   CsvAdd(row, eventName);
   CsvAdd(row, (string)eventTimeMs);
   CsvAdd(row, (string)heldMs);
   CsvAdd(row, (eventName == "START" ? "" : DoubleToString(grossPoints, 3)));
   CsvAdd(row, DoubleToString(path.mfe_points, 3));
   CsvAdd(row, DoubleToString(path.mae_points, 3));
   CsvAdd(row, (path.armed ? "true" : "false"));
   CsvAdd(row, (path.arm_time_msc > 0 ? (string)path.arm_time_msc : ""));
   CsvAdd(row, path.arm_rhythm);
   CsvAdd(row, path.current_rhythm);
   CsvAdd(row, DoubleToString(path.active_stop, _Digits));
   CsvAdd(row, (actualPositionOpen ? "true" : "false"));
   CsvAdd(row, (sampleValid ? "true" : "false"));
   CsvAdd(row, causalStatus);
   CsvAdd(row, THEORY_AI_T200_SHADOW_V2_CONTRACT_HASH);
   CsvAdd(row, "false");
   CsvAdd(row, "false");
   CsvAdd(row, (string)path.position_ticket);
   CsvAdd(row, (string)MagicNumber);
   CsvAdd(row, _Symbol);
   CsvAdd(row, closeMechanism);
   CsvAdd(row, (closePrice > 0.0 ? DoubleToString(closePrice, _Digits) : ""));
   CsvAdd(row, (closeTimeMsc > 0 ? (string)closeTimeMsc : ""));
   CsvAdd(row, (closingDealTicket > 0 ? (string)closingDealTicket : ""));
   CsvAdd(row, SAR_LIFECYCLE_RUN_TAG);
   CsvWriteLine(h, row);
   FileClose(h);
   return true;
}

//+------------------------------------------------------------------+
void AIT200ShadowStart(const ulong positionTicket,
                       const ulong positionIdentifier,
                       const long decisionTimeMs,
                       const long fillTimeMs,
                       const int side,
                       const double entryPrice,
                       const double initialSL,
                       const string route,
                       const string decisionIdentity)
{
   if(positionTicket == 0 || positionIdentifier == 0 ||
      fillTimeMs <= 0 || side == 0 || entryPrice <= 0.0 ||
      AIT200ShadowPathIndex(positionIdentifier) >= 0)
      return;

   TheoryAIT200ShadowV2Path path;
   path.position_ticket = positionTicket;
   path.position_identifier = positionIdentifier;
   path.decision_identity = decisionIdentity;
   path.route = route;
   path.decision_time_msc = decisionTimeMs;
   path.fill_time_msc = fillTimeMs;
   path.side = side;
   path.entry_price = entryPrice;
   path.initial_sl = initialSL;
   path.active_stop = initialSL;
   path.mfe_points = 0.0;
   path.mae_points = 0.0;
   path.initial_sl_valid = (initialSL > 0.0 &&
                            ((side > 0 && initialSL < entryPrice) ||
                             (side < 0 && initialSL > entryPrice)));
   path.start_logged = false;
   path.terminal_pending = false;
   path.pending_event = "";
   path.pending_event_time_msc = 0;
   path.pending_gross_points = 0.0;
   path.pending_sample_valid = false;
   path.pending_causal_status = "";
   path.armed = false;
   path.arm_time_msc = 0;
   path.arm_rhythm = "NOT_ARMED";
   path.current_rhythm = "INSUFFICIENT";

   path.start_logged = AIT200ShadowLog(
      path,
      "START",
      fillTimeMs,
      0.0,
      path.initial_sl_valid,
      (path.initial_sl_valid
       ? "ACTUAL_THEORY_FILL_SAME_BROKER_TICK_PATH"
       : "INVALID_ACTUAL_INITIAL_SL"));

   int n = ArraySize(aiT200ShadowPaths);
   ArrayResize(aiT200ShadowPaths, n + 1);
   aiT200ShadowPaths[n] = path;
}

//+------------------------------------------------------------------+
bool AIT200ShadowGrossAtOrBefore(const TheoryAIT200ShadowV2Path &path,
                                const long targetMs,
                                double &grossPoints,
                                long &sampleMs)
{
   for(int i = ArraySize(tickMs) - 1; i >= 0; i--)
   {
      if(tickMs[i] > targetMs)
         continue;
      if(tickMs[i] < path.fill_time_msc)
         return false;
      double halfSpread = tickSpread[i] * _Point * 0.5;
      double executable = (path.side > 0
                           ? tickMid[i] - halfSpread
                           : tickMid[i] + halfSpread);
      grossPoints = (path.side > 0
                     ? (executable - path.entry_price)
                     : (path.entry_price - executable)) / _Point;
      sampleMs = tickMs[i];
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
string AIT200ShadowRhythm(const TheoryAIT200ShadowV2Path &path,
                         const long nowMs,
                         const double currentGross)
{
   double priorFast = 0.0;
   double priorSlow = 0.0;
   long fastMs = 0;
   long slowMs = 0;
   bool fastValid = AIT200ShadowGrossAtOrBefore(path,
                                                nowMs - 500,
                                                priorFast,
                                                fastMs);
   bool slowValid = AIT200ShadowGrossAtOrBefore(path,
                                                nowMs - 1000,
                                                priorSlow,
                                                slowMs);
   if(!fastValid || !slowValid || fastMs >= nowMs || slowMs >= nowMs)
      return "INSUFFICIENT";

   double fastSeconds = (double)(nowMs - fastMs) / 1000.0;
   double slowSeconds = (double)(nowMs - slowMs) / 1000.0;
   if(fastSeconds <= 0.0 || slowSeconds <= 0.0)
      return "INSUFFICIENT";
   double fast = (currentGross - priorFast) / fastSeconds;
   double slow = (currentGross - priorSlow) / slowSeconds;
   double threshold = THEORY_AI_T200_SHADOW_VELOCITY_THRESHOLD;
   if(fast >= threshold && slow >= threshold)
      return "CONTINUATION";
   if(fast >= threshold && slow < 0.0)
      return "RECOVERY";
   if((fast <= -threshold && slow <= 0.0) ||
      (fast < 0.0 && slow < 0.0))
      return "DETERIORATION";
   if(MathAbs(fast) < threshold && MathAbs(slow) < threshold)
      return "STALL";
   return "TRANSITION";
}

//+------------------------------------------------------------------+
double AIT200ShadowTrailDistance(const string rhythm)
{
   if(rhythm == "CONTINUATION") return 120.0;
   if(rhythm == "RECOVERY") return 100.0;
   if(rhythm == "TRANSITION") return 80.0;
   if(rhythm == "STALL") return 60.0;
   if(rhythm == "DETERIORATION") return 40.0;
   return 80.0;
}

//+------------------------------------------------------------------+
bool AIT200ShadowTryTerminal(TheoryAIT200ShadowV2Path &path,
                             const string eventName,
                             const long eventTimeMs,
                             const double grossPoints,
                             const bool sampleValid,
                             const string causalStatus)
{
   if(!path.terminal_pending)
   {
      path.terminal_pending = true;
      path.pending_event = eventName;
      path.pending_event_time_msc = eventTimeMs;
      path.pending_gross_points = grossPoints;
      path.pending_sample_valid = sampleValid;
      path.pending_causal_status = causalStatus;
   }

   bool logged = AIT200ShadowLog(path,
                                 path.pending_event,
                                 path.pending_event_time_msc,
                                 path.pending_gross_points,
                                 path.pending_sample_valid,
                                 path.pending_causal_status);
   if(logged)
      path.terminal_pending = false;
   return logged;
}

//+------------------------------------------------------------------+
void AIT200ShadowUpdate(const MqlTick &t)
{
   long nowMs = t.time_msc;
   if(nowMs <= 0)
      return;

   for(int i = ArraySize(aiT200ShadowPaths) - 1; i >= 0; i--)
   {
      TheoryAIT200ShadowV2Path path = aiT200ShadowPaths[i];
      long heldMs = nowMs - path.fill_time_msc;
      if(heldMs < 0)
         continue;

      if(!path.start_logged)
      {
         path.start_logged = AIT200ShadowLog(
            path,
            "START",
            path.fill_time_msc,
            0.0,
            path.initial_sl_valid,
            (path.initial_sl_valid
             ? "ACTUAL_THEORY_FILL_SAME_BROKER_TICK_PATH"
             : "INVALID_ACTUAL_INITIAL_SL"));
         aiT200ShadowPaths[i] = path;
         if(!path.start_logged)
            continue;
      }

      if(path.terminal_pending)
      {
         if(AIT200ShadowTryTerminal(path,
                                    path.pending_event,
                                    path.pending_event_time_msc,
                                    path.pending_gross_points,
                                    path.pending_sample_valid,
                                    path.pending_causal_status))
            AIT200ShadowRemoveIndex(i);
         else
            aiT200ShadowPaths[i] = path;
         continue;
      }

      double executable = (path.side > 0 ? t.bid : t.ask);
      double gross = (path.side > 0
                      ? (executable - path.entry_price)
                      : (path.entry_price - executable)) / _Point;
      path.mfe_points = MathMax(path.mfe_points, gross);
      path.mae_points = MathMin(path.mae_points, gross);
      aiT200ShadowPaths[i] = path;

      if(!path.initial_sl_valid)
      {
         if(AIT200ShadowTryTerminal(path,
                                    "CENSORED_INVALID_INITIAL_SL",
                                    path.fill_time_msc,
                                    0.0,
                                    false,
                                    "INVALID_ACTUAL_INITIAL_SL"))
            AIT200ShadowRemoveIndex(i);
         else
            aiT200ShadowPaths[i] = path;
         continue;
      }

      if(heldMs > THEORY_AI_T200_SHADOW_HORIZON_MS +
                  THEORY_AI_T200_SHADOW_MAX_HORIZON_LAG_MS)
      {
         if(AIT200ShadowTryTerminal(path,
                                    "CENSORED_HORIZON_QUOTE_GAP",
                                    nowMs,
                                    gross,
                                    false,
                                    "FIRST_POST_HORIZON_QUOTE_TOO_LATE"))
            AIT200ShadowRemoveIndex(i);
         else
            aiT200ShadowPaths[i] = path;
         continue;
      }

      bool stopHit = (path.side > 0
                      ? executable <= path.active_stop
                      : executable >= path.active_stop);
      if(stopHit)
      {
         if(AIT200ShadowTryTerminal(path,
                                    (path.armed ? "TRAIL" : "SL"),
                                    nowMs,
                                    gross,
                                    true,
                                    "SAME_BROKER_EXECUTABLE_QUOTE"))
            AIT200ShadowRemoveIndex(i);
         else
            aiT200ShadowPaths[i] = path;
         continue;
      }

      if(gross >= THEORY_AI_T200_SHADOW_TRAIL_START_POINTS)
      {
         string rhythm = AIT200ShadowRhythm(path, nowMs, gross);
         double distance = AIT200ShadowTrailDistance(rhythm);
         double proposedStop = executable - path.side * distance * _Point;
         if(path.side > 0)
            path.active_stop = MathMax(path.active_stop, proposedStop);
         else
            path.active_stop = MathMin(path.active_stop, proposedStop);
         if(!path.armed)
         {
            path.armed = true;
            path.arm_time_msc = nowMs;
            path.arm_rhythm = rhythm;
         }
         path.current_rhythm = rhythm;
         aiT200ShadowPaths[i] = path;
      }

      if(heldMs >= THEORY_AI_T200_SHADOW_HORIZON_MS)
      {
         if(AIT200ShadowTryTerminal(path,
                                    "HORIZON",
                                    nowMs,
                                    gross,
                                    true,
                                    "SAME_BROKER_HORIZON_QUOTE_WITHIN_LAG"))
            AIT200ShadowRemoveIndex(i);
         else
            aiT200ShadowPaths[i] = path;
      }
   }
}

//+------------------------------------------------------------------+
void AIT200ShadowCensorAll(const string eventName)
{
   MqlTick t;
   bool tickValid = SymbolInfoTick(_Symbol, t) && t.time_msc > 0;
   long eventTimeMs = (tickValid ? t.time_msc : (long)TimeCurrent() * 1000);
   for(int i = ArraySize(aiT200ShadowPaths) - 1; i >= 0; i--)
   {
      TheoryAIT200ShadowV2Path path = aiT200ShadowPaths[i];
      double gross = 0.0;
      if(tickValid)
      {
         double executable = (path.side > 0 ? t.bid : t.ask);
         gross = (path.side > 0
                  ? (executable - path.entry_price)
                  : (path.entry_price - executable)) / _Point;
         path.mfe_points = MathMax(path.mfe_points, gross);
         path.mae_points = MathMin(path.mae_points, gross);
      }
      if(!path.start_logged)
         path.start_logged = AIT200ShadowLog(
            path,
            "START",
            path.fill_time_msc,
            0.0,
            path.initial_sl_valid,
            (path.initial_sl_valid
             ? "ACTUAL_THEORY_FILL_SAME_BROKER_TICK_PATH"
             : "INVALID_ACTUAL_INITIAL_SL"));
      if(!path.start_logged)
      {
         Print("AI T200 rhythm shadow START remained unwritten at deinit: ",
               (string)path.position_identifier);
         continue;
      }
      string finalEvent = (path.initial_sl_valid
                           ? eventName
                           : "CENSORED_INVALID_INITIAL_SL");
      string finalStatus = (path.initial_sl_valid
                            ? "EA_LIFECYCLE_CENSORING"
                            : "INVALID_ACTUAL_INITIAL_SL");
      for(int attempt = 0; attempt < 3; attempt++)
         if(AIT200ShadowTryTerminal(path,
                                    finalEvent,
                                    (path.initial_sl_valid
                                     ? eventTimeMs
                                     : path.fill_time_msc),
                                    (path.initial_sl_valid ? gross : 0.0),
                                    false,
                                    finalStatus))
            break;
   }
   ArrayResize(aiT200ShadowPaths, 0);
}

//+------------------------------------------------------------------+
string CurrentSessionBucket()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   if(dt.hour >= 0 && dt.hour < 7)
      return "ASIA";
   if(dt.hour >= 7 && dt.hour < 13)
      return "LONDON";
   if(dt.hour >= 13 && dt.hour < 21)
      return "NEW_YORK";
   return "LATE_US";
}

//+------------------------------------------------------------------+
string SpreadRegimeName(const double spreadPts)
{
   double base = (MaxSpreadPoints > 0.0 ? MaxSpreadPoints : 31.0);
   if(spreadPts <= base * 0.50)
      return "LOW";
   if(spreadPts <= base)
      return "NORMAL";
   if(spreadPts <= base * 1.50)
      return "WIDE";
   return "EXTREME";
}

//+------------------------------------------------------------------+
string TickJumpDirectionName(const int side, const double adverseDeltaPts)
{
   if(side == 0 || MathAbs(adverseDeltaPts) < 0.1)
      return "";

   bool jumpBuy = (side > 0 ? adverseDeltaPts < 0.0 : adverseDeltaPts > 0.0);
   return (jumpBuy ? "BUY" : "SELL");
}

//+------------------------------------------------------------------+
string TernaryFlagText(const int flag)
{
   if(flag < 0)
      return "";
   return (flag > 0 ? "true" : "false");
}

//+------------------------------------------------------------------+
bool LatestAdverseTickDeltaPoints(const int side, double &adverseDeltaPts)
{
   adverseDeltaPts = 0.0;
   int n = ArraySize(tickMs);
   if(side == 0 || n < 2)
      return false;

   double rawDeltaPts = (tickMid[n - 1] - tickMid[n - 2]) / _Point;
   double favorableDeltaPts = (side > 0 ? rawDeltaPts : -rawDeltaPts);
   adverseDeltaPts = -favorableDeltaPts;
   return true;
}

//+------------------------------------------------------------------+
void BuildJumpDirectionFlags(const bool hasDelta,
                             const double adverseDeltaPts,
                             int &withTrade,
                             int &againstTrade)
{
   withTrade = -1;
   againstTrade = -1;
   if(!hasDelta || MathAbs(adverseDeltaPts) < 0.1)
      return;

   withTrade = (adverseDeltaPts < -0.1 ? 1 : 0);
   againstTrade = (adverseDeltaPts > 0.1 ? 1 : 0);
}

//+------------------------------------------------------------------+
string OrderFlowAgreementDuringJump(const DirectionState &s, const string labels, const int side)
{
   if(side == 0)
      return "";
   if(StringFind(labels, "FLOW_DISAGREES") >= 0)
      return "false";
   if(StringFind(labels, "FLOW_AGREES") >= 0)
      return "true";
   if(s.flowFresh && s.flowDir != 0)
      return (s.flowDir == side ? "true" : "false");
   return "";
}

//+------------------------------------------------------------------+
void BuildV42JumpDirectionTelemetry(const bool active,
                                    const int side,
                                    const double adverseDeltaPts,
                                    const double favAt1s,
                                    const DirectionState &s,
                                    string &jumpDirection,
                                    string &withTrade,
                                    string &againstTrade,
                                    string &profit1s,
                                    string &loss1s,
                                    string &quality,
                                    string &flowAgreed)
{
   jumpDirection = "";
   withTrade = "";
   againstTrade = "";
   profit1s = "";
   loss1s = "";
   quality = "";
   flowAgreed = "";

   if(!UseV42JumpDirectionTelemetry || !active || side == 0)
      return;

   double absDelta = MathAbs(adverseDeltaPts);
   if(absDelta < 0.1)
      return;

   bool hasFav1s = (favAt1s < ROUTER_BIG_VALUE * 0.5);
   bool jumpWithTrade = (adverseDeltaPts < -0.1);
   bool jumpAgainstTrade = (adverseDeltaPts > 0.1);

   jumpDirection = TickJumpDirectionName(side, adverseDeltaPts);
   withTrade = (jumpWithTrade ? "true" : "false");
   againstTrade = (jumpAgainstTrade ? "true" : "false");
   if(hasFav1s)
   {
      profit1s = (favAt1s > 0.0 ? "true" : "false");
      loss1s = (favAt1s < 0.0 ? "true" : "false");
   }

   if(jumpWithTrade && hasFav1s && favAt1s > 0.0)
      quality = "CONTINUATION_HINT";
   else if(jumpWithTrade && hasFav1s)
      quality = "FAILED_FOLLOW";
   else if(jumpAgainstTrade && hasFav1s && favAt1s < 0.0)
      quality = "EXHAUSTION_DANGER";
   else if(jumpAgainstTrade && hasFav1s)
      quality = "SNAPBACK_RECOVERY";
   else if(jumpWithTrade)
      quality = "WITH_TRADE_PENDING";
   else if(jumpAgainstTrade)
      quality = "AGAINST_TRADE_PENDING";

   flowAgreed = OrderFlowAgreementDuringJump(s, s.labels, side);
}

//+------------------------------------------------------------------+
void ClearTradeMeasurementContext()
{
   logTradeMeasurementActive = false;
   logRuleTelemetryActive = false;
   logDealLedgerActive = false;
   logLifecyclePositionTicket = 0;
   logLifecycleCloseMechanism = "";
   logLifecycleClosePrice = 0.0;
   logLifecycleCloseServerTimeMsc = 0;
   logLifecycleClosingDealTicket = 0;
   logDealCostsComplete = false;
   logDealPositionIdentifier = 0;
   logDealLedgerDeals = 0;
   logDealProfitMoney = 0.0;
   logDealCommissionMoney = 0.0;
   logDealSwapMoney = 0.0;
   logDealFeeMoney = 0.0;
   logDealNetMoney = 0.0;
   logRequestedPrice = 0.0;
   logExecutedPrice = 0.0;
   logSlippagePoints = 0.0;
   logAdverseSlippagePoints = 0.0;
   logRuleTrueMs = 0;
   logOrderSendMs = 0;
   logFillMs = 0;
   logRuleSide = 0;
   logRuleTruePrice = 0.0;
   logSpreadAtRuleTrue = 0.0;
   logSpreadAtSend = 0.0;
   logSpreadAtFill = 0.0;
   logDecisionDriftPoints = 0.0;
   logTimeInTradeSeconds = 0.0;
   logMfeBeforeClose = 0.0;
   logMaeBeforeClose = 0.0;
   logFirst10sMfe = 0.0;
   logFreezeLevelPoints = 0.0;
   logWarningLevelPoints = 0.0;
   logMaxSingleTickAdversePts = 0.0;
   logTicksFromFillToWarn24 = 0;
   logMsFromFillToWarn15 = 0;
   logMsFromFillToWarn18 = 0;
   logMsFromFillToWarn21 = 0;
   logMsFromFillToWarn24 = 0;
   logFavAt1s = ROUTER_BIG_VALUE;
   logFavAt2s = ROUTER_BIG_VALUE;
   logFavAt3s = ROUTER_BIG_VALUE;
   logQuoteGapMs = 0;
   logLastTickDeltaPts = 0.0;
   logRetryCount = 0;
   logMsInFrozenState = 0;
   logSessionBucket = "";
   logSpreadRegime = "";
   logTickJumpDirection = "";
   logTickJumpWithTrade = "";
   logTickJumpAgainstTrade = "";
   logJumpFollowedByProfit1s = "";
   logJumpFollowedByLoss1s = "";
   logSessionJumpQuality = "";
   logOrderFlowAgreedDuringJump = "";
   logEntryTickJumpWithTrade = "";
   logEntryTickJumpAgainstTrade = "";
   logFirst500msMaxAdverseJumpPts = 0.0;
   logFirst1sMaxAdverseJumpPts = 0.0;
   logFirst2sMaxAdverseJumpPts = 0.0;
   logPreWarn15JumpAgainstTrade = "";
   logPreWarn18JumpAgainstTrade = "";
   logPreWarn21JumpAgainstTrade = "";
   logPreWarn24JumpAgainstTrade = "";
   logClosedBeforeSnapshot = "";
   logV44ShadowFirst1sFired = "";
   logV44ShadowFirst1sMs = 0;
   logV44ShadowFirst1sFav = 0.0;
   logV44ShadowFirst1sReplayDelta = 0.0;
   logV44ShadowFirst2sFired = "";
   logV44ShadowFirst2sMs = 0;
   logV44ShadowFirst2sFav = 0.0;
   logV44ShadowFirst2sReplayDelta = 0.0;
   logV44FOLMSGhostStarted = "";
   ClearV451ProofTelemetryLog();
   logV45FOLMQualityScore = "";
   logV45FOLMQualityBucket = "";
   logV45FOLMLowQualityWouldBlock = "";
   logV45FOLMLowQualityReplayDelta = "";
   logV45FOLMFav2sBucket = "";
   logV45FOLMFav3sBucket = "";
   logV45FOLMFirst10sMfeBucket = "";
   ClearV452LowWinnerMicroscopeLog();
   ClearV46LowDeadShadowReplayLog();
   ClearV461MicroTelemetryLog();
   ClearV47DecisionFrontierLog();
   ClearV45PreEntryHighShadowLog();
   ClearV48Mode2ScorecardLog();
   logBidAtRequest = 0.0;
   logAskAtRequest = 0.0;
   logSpreadAtRequest = 0.0;
   logVelocity1s = 0.0;
   logVelocity3s = 0.0;
   logVelocity5s = 0.0;
   logTradeRetcode = 0;
}

//+------------------------------------------------------------------+
void CaptureRuleTelemetry(const ulong ticket,
                          const int idx,
                          const double fav,
                          const long heldMs,
                          const string tag,
                          const double warningLevel,
                          const string warningFamily)
{
   if(!UsePassiveWarningTelemetry && warningLevel > 0.0)
      return;

   MqlTick t;
   if(!SymbolInfoTick(_Symbol, t))
      return;

   int side = 0;
   if(idx >= 0 && idx < ArraySize(trackedSides))
      side = trackedSides[idx];
   else if(ticket > 0 && PositionSelectByTicket(ticket))
      side = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1);

   double rulePrice = 0.0;
   if(side > 0)
      rulePrice = t.bid;
   else if(side < 0)
      rulePrice = t.ask;
   else
      rulePrice = (t.ask + t.bid) * 0.5;

   logRuleTelemetryActive = true;
   logRuleTrueMs = t.time_msc;
   logRuleSide = side;
   logRuleTruePrice = NormalizeDouble(rulePrice, _Digits);
   logSpreadAtRuleTrue = (t.ask - t.bid) / _Point;
   logTimeInTradeSeconds = (heldMs > 0 ? (double)heldMs / 1000.0 : 0.0);
   logFreezeLevelPoints = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   logWarningLevelPoints = warningLevel;
   logSessionBucket = CurrentSessionBucket();
   logSpreadRegime = SpreadRegimeName(logSpreadAtRuleTrue);
   if(StringLen(tag) == 0 || StringLen(warningFamily) == 0)
   {
      // Event name and reason text carry the tag/family for offline replay.
   }

   if(idx >= 0 && idx < ArraySize(trackedTickets))
   {
      logMfeBeforeClose = trackedMfes[idx];
      logMaeBeforeClose = trackedMaes[idx];
      logFirst10sMfe = trackedFirst10sMfes[idx];
      logMaxSingleTickAdversePts = trackedMaxSingleTickAdversePts[idx];
      logTicksFromFillToWarn24 = trackedFOLMWarn24Ticks[idx];
      logMsFromFillToWarn15 = trackedFOLMWarn15Ms[idx];
      logMsFromFillToWarn18 = trackedFOLMWarn18Ms[idx];
      logMsFromFillToWarn21 = trackedFOLMWarn21Ms[idx];
      logMsFromFillToWarn24 = trackedFOLMWarn24Ms[idx];
      logFavAt1s = trackedFavAt1s[idx];
      logFavAt2s = trackedFavAt2s[idx];
      logFavAt3s = trackedFavAt3s[idx];
      SetV45PreEntryHighShadowLog(trackedPreEntryHighShadowScores[idx],
                                  trackedPreEntryHighShadowBuckets[idx],
                                  trackedPreEntryHighWouldAllows[idx],
                                  trackedPreEntryHighWouldBlocks[idx],
                                  trackedPreEntryHighSignals[idx]);
      SetV48Mode2ScorecardLog(trackedV48Mode2Signal[idx],
                              trackedV48Mode2BlockReason[idx],
                              trackedV48Mode2OppFlags[idx],
                              trackedV48Mode2Velocity1s[idx],
                              trackedV48Mode2WeightFactor[idx]);
      logQuoteGapMs = trackedLastQuoteGapMs[idx];
      logLastTickDeltaPts = trackedLastTickDeltaPts[idx];
      if(UseV43EarlyJumpTelemetry)
      {
         logEntryTickJumpWithTrade = TernaryFlagText(trackedEntryTickJumpWithTrades[idx]);
         logEntryTickJumpAgainstTrade = TernaryFlagText(trackedEntryTickJumpAgainstTrades[idx]);
         logFirst500msMaxAdverseJumpPts = trackedFirst500msMaxAdverseJumpPts[idx];
         logFirst1sMaxAdverseJumpPts = trackedFirst1sMaxAdverseJumpPts[idx];
         logFirst2sMaxAdverseJumpPts = trackedFirst2sMaxAdverseJumpPts[idx];
         logPreWarn15JumpAgainstTrade = TernaryFlagText(trackedPreWarn15JumpAgainstTrades[idx]);
         logPreWarn18JumpAgainstTrade = TernaryFlagText(trackedPreWarn18JumpAgainstTrades[idx]);
         logPreWarn21JumpAgainstTrade = TernaryFlagText(trackedPreWarn21JumpAgainstTrades[idx]);
         logPreWarn24JumpAgainstTrade = TernaryFlagText(trackedPreWarn24JumpAgainstTrades[idx]);
         logClosedBeforeSnapshot = (trackedFavAt1s[idx] > ROUTER_BIG_VALUE * 0.5 ? "true" : "false");
      }
      if(UseV44ShadowReplayTelemetry)
      {
         logV44ShadowFirst1sFired = (trackedV44First1sShadowFired[idx] ? "true" : "false");
         logV44ShadowFirst1sMs = trackedV44First1sShadowMs[idx];
         logV44ShadowFirst1sFav = trackedV44First1sShadowFav[idx];
         logV44ShadowFirst1sReplayDelta = (trackedV44First1sShadowFired[idx]
                                           ? trackedV44First1sShadowFav[idx] - fav
                                           : 0.0);
         logV44ShadowFirst2sFired = (trackedV44First2sShadowFired[idx] ? "true" : "false");
         logV44ShadowFirst2sMs = trackedV44First2sShadowMs[idx];
         logV44ShadowFirst2sFav = trackedV44First2sShadowFav[idx];
         logV44ShadowFirst2sReplayDelta = (trackedV44First2sShadowFired[idx]
                                           ? trackedV44First2sShadowFav[idx] - fav
                                           : 0.0);
         logV44FOLMSGhostStarted = (TrackedLabelHas(idx, "V44_FOLM_SM_GHOST_ARMED") ? "true" : "false");
      }
      if(UseV451ProofTelemetry)
      {
         logV451LowJFirst1sFired = (trackedV451LowJFirst1sFired[idx] ? "true" : "false");
         logV451LowJFirst1sMs = trackedV451LowJFirst1sMs[idx];
         logV451LowJFirst1sFav = trackedV451LowJFirst1sFav[idx];
         logV451LowJFirst1sReplayDelta = (trackedV451LowJFirst1sFired[idx]
                                           ? trackedV451LowJFirst1sFav[idx] - fav
                                           : 0.0);
         logV451LowJFirst1sLeadMs = (trackedV451LowJFirst1sFired[idx] && heldMs > trackedV451LowJFirst1sMs[idx]
                                     ? heldMs - trackedV451LowJFirst1sMs[idx]
                                     : 0);
         logV451LowJFirst1sBeforeCurrentShield = (trackedV451LowJFirst1sFired[idx]
                                                  ? (logV451LowJFirst1sLeadMs > 0 ? "true" : "false")
                                                  : "");

         logV451LowJFirst2sFired = (trackedV451LowJFirst2sFired[idx] ? "true" : "false");
         logV451LowJFirst2sMs = trackedV451LowJFirst2sMs[idx];
         logV451LowJFirst2sFav = trackedV451LowJFirst2sFav[idx];
         logV451LowJFirst2sReplayDelta = (trackedV451LowJFirst2sFired[idx]
                                           ? trackedV451LowJFirst2sFav[idx] - fav
                                           : 0.0);
         logV451LowJFirst2sLeadMs = (trackedV451LowJFirst2sFired[idx] && heldMs > trackedV451LowJFirst2sMs[idx]
                                     ? heldMs - trackedV451LowJFirst2sMs[idx]
                                     : 0);
         logV451LowJFirst2sBeforeCurrentShield = (trackedV451LowJFirst2sFired[idx]
                                                  ? (logV451LowJFirst2sLeadMs > 0 ? "true" : "false")
                                                  : "");

         logV451ActualCloseEvent = tag;
         logV451ActualCloseFav = fav;
         logV451ActualCloseHeldMs = heldMs;
         if(StringLen(trackedV451FlowOppSourceTiming[idx]) > 0)
         {
            logV451FlowOppSourceTiming = trackedV451FlowOppSourceTiming[idx];
            logV451FlowOppSourceMs = trackedV451FlowOppSourceMs[idx];
            logV451FlowOppSourceFav = trackedV451FlowOppSourceFav[idx];
            logV451FlowOppAuditFlag = (trackedV451FlowOppSourceMs[idx] <= 3000 ? "early_source" : "late_source");
         }
         else if(V451LabelsHaveFlowOppPressure(trackedLabels[idx]))
         {
            logV451FlowOppSourceTiming = "close";
            logV451FlowOppSourceMs = heldMs;
            logV451FlowOppSourceFav = fav;
            logV451FlowOppAuditFlag = "close_label_only";
         }
         else
            logV451FlowOppAuditFlag = "not_seen";
      }
      if(UseV46LowDeadShadowReplay)
      {
         logV46LowDeadShadowFired = (trackedV46LowDeadShadowFired[idx] ? "true" : "false");
         logV46LowDeadShadowMs = trackedV46LowDeadShadowMs[idx];
         logV46LowDeadShadowFav = trackedV46LowDeadShadowFav[idx];
         logV46LowDeadShadowMfe = trackedV46LowDeadShadowMfe[idx];
         logV46LowDeadShadowMaxFav1To3 = trackedV46LowDeadShadowMaxFav1To3[idx];
         logV46LowDeadShadowReplayDelta = (trackedV46LowDeadShadowFired[idx]
                                           ? trackedV46LowDeadShadowFav[idx] - fav
                                           : 0.0);
         logV46LowDeadShadowLeadMs = (trackedV46LowDeadShadowFired[idx] && heldMs > trackedV46LowDeadShadowMs[idx]
                                      ? heldMs - trackedV46LowDeadShadowMs[idx]
                                      : 0);
         logV46LowDeadShadowBeforeCurrentShield = (trackedV46LowDeadShadowFired[idx]
                                                   ? (logV46LowDeadShadowLeadMs > 0 ? "true" : "false")
                                                   : "");
         logV46LowDeadShadowFinalPath = V452FinalPathName(tag, fav);
         logV46LowDeadShadowSpeedTouched = (trackedV46LowDeadShadowFired[idx] && logV46LowDeadShadowFinalPath == "SPEED"
                                            ? "true"
                                            : (trackedV46LowDeadShadowFired[idx] ? "false" : ""));
         logV46LowDeadShadowReason = trackedV46LowDeadShadowReason[idx];
      }
      logRetryCount = trackedHardFloorAttempts[idx];
      if(trackedRetestCollapseAttempts[idx] > logRetryCount)
         logRetryCount = trackedRetestCollapseAttempts[idx];
      if(trackedPreSpeedDefenseAttempts[idx] > logRetryCount)
         logRetryCount = trackedPreSpeedDefenseAttempts[idx];
      if(trackedUrgentCloseStartMs[idx] > 0)
      {
         logMsInFrozenState = t.time_msc - trackedUrgentCloseStartMs[idx];
         if(logMsInFrozenState < 0)
            logMsInFrozenState = 0;
      }
   }
   else
   {
      logMfeBeforeClose = fav;
      logMaeBeforeClose = fav;
      logFirst10sMfe = 0.0;
      ClearV45PreEntryHighShadowLog();
   }

   RecordFirstProfitTelemetry(idx, heldMs, fav, true);

   bool isFOLM = (idx >= 0 && idx < ArraySize(trackedLabels) && TrackedLabelHas(idx, "SAR:FOLM"));
   string labelsForV452 = (idx >= 0 && idx < ArraySize(trackedLabels) ? trackedLabels[idx] : "");
   BuildV45FOLMQualityTelemetry(isFOLM, fav, logFavAt2s, logFavAt3s, logFirst10sMfe);
   BuildV452LowWinnerMicroscopeTelemetry(isFOLM,
                                         tag,
                                         fav,
                                         labelsForV452,
                                         logV45FOLMQualityBucket,
                                         logFavAt1s,
                                         logFavAt2s,
                                         logFavAt3s,
                                         logFirst10sMfe,
                                         logFirst1sMaxAdverseJumpPts,
                                         logFirst2sMaxAdverseJumpPts,
                                         logV451FlowOppSourceTiming,
                                         logV451FlowOppSourceMs);
   BuildV461MicroTelemetry(idx,
                           isFOLM,
                           tag,
                           fav,
                           heldMs,
                           labelsForV452,
                           logV45FOLMQualityBucket);
   BuildV47DecisionFrontierTelemetry(idx,
                                     isFOLM,
                                     tag,
                                     fav,
                                     heldMs,
                                     labelsForV452,
                                     logV45FOLMQualityBucket);
   BuildV471TelemetryRepair(idx,
                            isFOLM,
                            tag,
                            fav,
                            heldMs,
                            logV45FOLMQualityBucket);
}

//+------------------------------------------------------------------+
void PrimeActiveCloseTelemetry(const ulong ticket,
                               const int idx,
                               const double fav,
                               const long heldMs,
                               const string tag,
                               const double warningLevel,
                               const string warningFamily)
{
   CaptureRuleTelemetry(ticket, idx, fav, heldMs, tag, 0.0, warningFamily);
   if(logRuleTelemetryActive && warningLevel > 0.0)
      logWarningLevelPoints = warningLevel;
}

//+------------------------------------------------------------------+
void CaptureAutoCloseRuleTelemetry(const ulong ticket,
                                   const int side,
                                   const MqlTick &t,
                                   const double requestPrice)
{
   if(logRuleTelemetryActive)
      return;

   int idx = TrackerIndex(ticket);
   double fav = 0.0;
   long heldMs = 0;
   if(idx >= 0)
   {
      double current = (side > 0 ? t.bid : t.ask);
      fav = (side > 0 ? (current - trackedEntries[idx]) : (trackedEntries[idx] - current)) / _Point;
      heldMs = t.time_msc - trackedEntryMs[idx];
   }

   CaptureRuleTelemetry(ticket, idx, fav, heldMs, "ACTIVE_CLOSE_REQUEST", 0.0, "ACTIVE_CLOSE");
   if(logRuleTruePrice <= 0.0 && requestPrice > 0.0)
      logRuleTruePrice = requestPrice;
}

//+------------------------------------------------------------------+
void CaptureTradeMeasurement(const double requestedPrice,
                             const double executedPrice,
                             const int side,
                             const bool isExit,
                             const MqlTick &requestTick,
                             const uint retcode)
{
   if(!LogSlippageMeasurement)
      return;

   logTradeMeasurementActive = true;
   logRequestedPrice = requestedPrice;
   logExecutedPrice = executedPrice;
   logBidAtRequest = requestTick.bid;
   logAskAtRequest = requestTick.ask;
   logSpreadAtRequest = (requestTick.ask - requestTick.bid) / _Point;
   logTradeRetcode = retcode;

   double mid = (requestTick.ask + requestTick.bid) * 0.5;
   logVelocity1s = SignedVelocityPointsPerSecond(mid, requestTick.time_msc, 1000);
   logVelocity3s = SignedVelocityPointsPerSecond(mid, requestTick.time_msc, 3000);
   logVelocity5s = SignedVelocityPointsPerSecond(mid, requestTick.time_msc, 5000);

   if(logRuleTelemetryActive)
   {
      logOrderSendMs = requestTick.time_msc;
      logSpreadAtSend = logSpreadAtRequest;
      MqlTick fillTick;
      if(SymbolInfoTick(_Symbol, fillTick))
      {
         logFillMs = fillTick.time_msc;
         logSpreadAtFill = (fillTick.ask - fillTick.bid) / _Point;
      }
      else
         logFillMs = GetTickMs();

      if(logRuleTruePrice > 0.0 && requestedPrice > 0.0)
      {
         int driftSide = (logRuleSide != 0 ? logRuleSide : side);
         logDecisionDriftPoints = (driftSide > 0
                                   ? (logRuleTruePrice - requestedPrice)
                                   : (requestedPrice - logRuleTruePrice)) / _Point;
      }
   }

   if(requestedPrice <= 0.0 || executedPrice <= 0.0 || side == 0)
   {
      logSlippagePoints = 0.0;
      logAdverseSlippagePoints = 0.0;
      return;
   }

   logSlippagePoints = (executedPrice - requestedPrice) / _Point;
   if(isExit)
      logAdverseSlippagePoints = (side > 0 ? requestedPrice - executedPrice : executedPrice - requestedPrice) / _Point;
   else
      logAdverseSlippagePoints = (side > 0 ? executedPrice - requestedPrice : requestedPrice - executedPrice) / _Point;
}

//+------------------------------------------------------------------+
double DealPriceOrFallback(const ulong dealTicket, const double resultPrice, const double fallbackPrice)
{
   if(dealTicket > 0 && HistoryDealSelect(dealTicket))
   {
      double dealPrice = HistoryDealGetDouble(dealTicket, DEAL_PRICE);
      if(dealPrice > 0.0)
         return dealPrice;
   }
   if(resultPrice > 0.0)
      return resultPrice;
   return fallbackPrice;
}

//+------------------------------------------------------------------+
string CloseMechanismFromDealReason(const long dealReason)
{
   if(dealReason == DEAL_REASON_SL)
      return "STOP_LOSS";
   if(dealReason == DEAL_REASON_TP)
      return "TAKE_PROFIT";
   if(dealReason == DEAL_REASON_SO)
      return "MARGIN_CALL";
   if(dealReason == DEAL_REASON_CLIENT || dealReason == DEAL_REASON_MOBILE || dealReason == DEAL_REASON_WEB)
      return "MANUAL";
   if(dealReason == DEAL_REASON_EXPERT)
      return "EA_CLOSE";
   return "EA_CLOSE";
}

//+------------------------------------------------------------------+
void CaptureCloseLifecycleFields(const ulong positionTicket,
                                 const ulong dealTicket,
                                 const double fallbackClosePrice,
                                 const long fallbackCloseTimeMsc)
{
   logLifecyclePositionTicket = positionTicket;
   logLifecycleClosingDealTicket = dealTicket;
   logLifecycleClosePrice = fallbackClosePrice;
   logLifecycleCloseServerTimeMsc = fallbackCloseTimeMsc;
   logLifecycleCloseMechanism = "EA_CLOSE";

   if(dealTicket > 0 && HistoryDealSelect(dealTicket))
   {
      double dealPrice = HistoryDealGetDouble(dealTicket, DEAL_PRICE);
      long dealTimeMsc = (long)HistoryDealGetInteger(dealTicket, DEAL_TIME_MSC);
      if(dealPrice > 0.0)
         logLifecycleClosePrice = dealPrice;
      if(dealTimeMsc > 0)
         logLifecycleCloseServerTimeMsc = dealTimeMsc;
      logLifecycleCloseMechanism =
         CloseMechanismFromDealReason(HistoryDealGetInteger(dealTicket, DEAL_REASON));
   }

   if(logLifecycleCloseServerTimeMsc <= 0)
      logLifecycleCloseServerTimeMsc = GetTickMs();
}

//+------------------------------------------------------------------+
string CloseMechanismForLogRow(const string eventName, const string reason)
{
   if(StringLen(logLifecycleCloseMechanism) > 0)
      return logLifecycleCloseMechanism;
   if(StringFind(eventName, "TRAIL") >= 0 || StringFind(reason, "trail") >= 0)
      return "TRAILING_STOP";
   if(StringFind(eventName, "TAKE_PROFIT") >= 0 || StringFind(reason, "take_profit") >= 0)
      return "TAKE_PROFIT";
   if(StringFind(eventName, "STOP_LOSS") >= 0 || StringFind(reason, "stop_loss") >= 0)
      return "STOP_LOSS";
   if(StringFind(eventName, "MARGIN") >= 0 || StringFind(reason, "margin") >= 0)
      return "MARGIN_CALL";
   if(StringFind(eventName, "MANUAL") >= 0 || StringFind(reason, "manual") >= 0)
      return "MANUAL";
   return "EA_CLOSE";
}

//+------------------------------------------------------------------+
bool CapturePositionDealLedger(const long positionIdentifier, const bool costsComplete)
{
   logDealLedgerActive = false;
   logDealCostsComplete = false;
   logDealPositionIdentifier = positionIdentifier;
   logDealLedgerDeals = 0;
   logDealProfitMoney = 0.0;
   logDealCommissionMoney = 0.0;
   logDealSwapMoney = 0.0;
   logDealFeeMoney = 0.0;
   logDealNetMoney = 0.0;

   if(positionIdentifier <= 0 || !HistorySelectByPosition(positionIdentifier))
      return false;

   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong dealTicket = HistoryDealGetTicket(i);
      if(dealTicket == 0)
         continue;
      logDealProfitMoney += HistoryDealGetDouble(dealTicket, DEAL_PROFIT);
      logDealCommissionMoney += HistoryDealGetDouble(dealTicket, DEAL_COMMISSION);
      logDealSwapMoney += HistoryDealGetDouble(dealTicket, DEAL_SWAP);
      logDealFeeMoney += HistoryDealGetDouble(dealTicket, DEAL_FEE);
      logDealLedgerDeals++;
   }

   if(logDealLedgerDeals <= 0)
      return false;

   logDealNetMoney = logDealProfitMoney + logDealCommissionMoney +
                     logDealSwapMoney + logDealFeeMoney;
   logDealCostsComplete = costsComplete;
   logDealLedgerActive = true;
   return true;
}

//+------------------------------------------------------------------+
void PendingRequestAdd(const ulong orderTicket,
                       const RouterAction action,
                       const double requestedPrice,
                       const long decisionMs,
                       const double preEntryScore,
                       const string preEntryBucket,
                       const string preEntryAllow,
                       const string preEntryBlock,
                       const string preEntrySignals,
                       const string v471TapeHealth,
                       const double v471VelocityDecay,
                       const long v471PreSpeedSignalAgeMs,
                       const string v48Mode2Signal,
                       const string v48Mode2BlockReason,
                       const int v48Mode2OppFlags,
                       const double v48Mode2Velocity1s,
                       const double v48Mode2WeightFactor,
                       const TheoryAIPreEntryJourneyContextV1 &aiJourneyContext)
{
   if(orderTicket == 0 || action == ActSkip)
      return;

   int n = ArraySize(pendingRequestTickets);
   ArrayResize(pendingRequestTickets, n + 1);
   ArrayResize(pendingRequestPrices, n + 1);
   ArrayResize(pendingRequestActions, n + 1);
   ArrayResize(pendingRequestDecisionMs, n + 1);
   ArrayResize(pendingRequestAIJourneyContexts, n + 1);
   ArrayResize(pendingRequestPreEntryHighScores, n + 1);
   ArrayResize(pendingRequestPreEntryHighBuckets, n + 1);
   ArrayResize(pendingRequestPreEntryHighAllows, n + 1);
   ArrayResize(pendingRequestPreEntryHighBlocks, n + 1);
   ArrayResize(pendingRequestPreEntryHighSignals, n + 1);
   ArrayResize(pendingRequestV471TapeHealth, n + 1);
   ArrayResize(pendingRequestV471VelocityDecay, n + 1);
   ArrayResize(pendingRequestV471PreSpeedSignalAgeMs, n + 1);
   ArrayResize(pendingRequestV48Mode2Signal, n + 1);
   ArrayResize(pendingRequestV48Mode2BlockReason, n + 1);
   ArrayResize(pendingRequestV48Mode2OppFlags, n + 1);
   ArrayResize(pendingRequestV48Mode2Velocity1s, n + 1);
   ArrayResize(pendingRequestV48Mode2WeightFactor, n + 1);
   pendingRequestTickets[n] = orderTicket;
   pendingRequestPrices[n] = requestedPrice;
   pendingRequestActions[n] = (int)action;
   pendingRequestDecisionMs[n] = decisionMs;
   pendingRequestAIJourneyContexts[n] = aiJourneyContext;
   pendingRequestPreEntryHighScores[n] = preEntryScore;
   pendingRequestPreEntryHighBuckets[n] = preEntryBucket;
   pendingRequestPreEntryHighAllows[n] = preEntryAllow;
   pendingRequestPreEntryHighBlocks[n] = preEntryBlock;
   pendingRequestPreEntryHighSignals[n] = preEntrySignals;
   pendingRequestV471TapeHealth[n] = v471TapeHealth;
   pendingRequestV471VelocityDecay[n] = v471VelocityDecay;
   pendingRequestV471PreSpeedSignalAgeMs[n] = v471PreSpeedSignalAgeMs;
   pendingRequestV48Mode2Signal[n] = v48Mode2Signal;
   pendingRequestV48Mode2BlockReason[n] = v48Mode2BlockReason;
   pendingRequestV48Mode2OppFlags[n] = v48Mode2OppFlags;
   pendingRequestV48Mode2Velocity1s[n] = v48Mode2Velocity1s;
   pendingRequestV48Mode2WeightFactor[n] = v48Mode2WeightFactor;
}

//+------------------------------------------------------------------+
void PendingRequestRemoveIndex(const int idx)
{
   int n = ArraySize(pendingRequestTickets);
   if(idx < 0 || idx >= n)
      return;

   for(int i = idx; i < n - 1; i++)
   {
      pendingRequestTickets[i] = pendingRequestTickets[i + 1];
      pendingRequestPrices[i] = pendingRequestPrices[i + 1];
      pendingRequestActions[i] = pendingRequestActions[i + 1];
      pendingRequestDecisionMs[i] = pendingRequestDecisionMs[i + 1];
      pendingRequestAIJourneyContexts[i] =
         pendingRequestAIJourneyContexts[i + 1];
      pendingRequestPreEntryHighScores[i] = pendingRequestPreEntryHighScores[i + 1];
      pendingRequestPreEntryHighBuckets[i] = pendingRequestPreEntryHighBuckets[i + 1];
      pendingRequestPreEntryHighAllows[i] = pendingRequestPreEntryHighAllows[i + 1];
      pendingRequestPreEntryHighBlocks[i] = pendingRequestPreEntryHighBlocks[i + 1];
      pendingRequestPreEntryHighSignals[i] = pendingRequestPreEntryHighSignals[i + 1];
      pendingRequestV471TapeHealth[i] = pendingRequestV471TapeHealth[i + 1];
      pendingRequestV471VelocityDecay[i] = pendingRequestV471VelocityDecay[i + 1];
      pendingRequestV471PreSpeedSignalAgeMs[i] = pendingRequestV471PreSpeedSignalAgeMs[i + 1];
      pendingRequestV48Mode2Signal[i] = pendingRequestV48Mode2Signal[i + 1];
      pendingRequestV48Mode2BlockReason[i] = pendingRequestV48Mode2BlockReason[i + 1];
      pendingRequestV48Mode2OppFlags[i] = pendingRequestV48Mode2OppFlags[i + 1];
      pendingRequestV48Mode2Velocity1s[i] = pendingRequestV48Mode2Velocity1s[i + 1];
      pendingRequestV48Mode2WeightFactor[i] = pendingRequestV48Mode2WeightFactor[i + 1];
   }
   ArrayResize(pendingRequestTickets, n - 1);
   ArrayResize(pendingRequestPrices, n - 1);
   ArrayResize(pendingRequestActions, n - 1);
   ArrayResize(pendingRequestDecisionMs, n - 1);
   ArrayResize(pendingRequestAIJourneyContexts, n - 1);
   ArrayResize(pendingRequestPreEntryHighScores, n - 1);
   ArrayResize(pendingRequestPreEntryHighBuckets, n - 1);
   ArrayResize(pendingRequestPreEntryHighAllows, n - 1);
   ArrayResize(pendingRequestPreEntryHighBlocks, n - 1);
   ArrayResize(pendingRequestPreEntryHighSignals, n - 1);
   ArrayResize(pendingRequestV471TapeHealth, n - 1);
   ArrayResize(pendingRequestV471VelocityDecay, n - 1);
   ArrayResize(pendingRequestV471PreSpeedSignalAgeMs, n - 1);
   ArrayResize(pendingRequestV48Mode2Signal, n - 1);
   ArrayResize(pendingRequestV48Mode2BlockReason, n - 1);
   ArrayResize(pendingRequestV48Mode2OppFlags, n - 1);
   ArrayResize(pendingRequestV48Mode2Velocity1s, n - 1);
   ArrayResize(pendingRequestV48Mode2WeightFactor, n - 1);
}

//+------------------------------------------------------------------+
void PendingRequestRemoveTicket(const ulong orderTicket)
{
   for(int i = ArraySize(pendingRequestTickets) - 1; i >= 0; i--)
      if(pendingRequestTickets[i] == orderTicket)
         PendingRequestRemoveIndex(i);
}

//+------------------------------------------------------------------+
void PendingRequestCopyShadow(const int idx,
                              double &preEntryScore,
                              string &preEntryBucket,
                              string &preEntryAllow,
                              string &preEntryBlock,
                              string &preEntrySignals,
                              string &v471TapeHealth,
                              double &v471VelocityDecay,
                              long &v471PreSpeedSignalAgeMs,
                              string &v48Mode2Signal,
                              string &v48Mode2BlockReason,
                              int &v48Mode2OppFlags,
                              double &v48Mode2Velocity1s,
                              double &v48Mode2WeightFactor,
                              TheoryAIPreEntryJourneyContextV1 &aiJourneyContext)
{
   preEntryScore = pendingRequestPreEntryHighScores[idx];
   preEntryBucket = pendingRequestPreEntryHighBuckets[idx];
   preEntryAllow = pendingRequestPreEntryHighAllows[idx];
   preEntryBlock = pendingRequestPreEntryHighBlocks[idx];
   preEntrySignals = pendingRequestPreEntryHighSignals[idx];
   v471TapeHealth = pendingRequestV471TapeHealth[idx];
   v471VelocityDecay = pendingRequestV471VelocityDecay[idx];
   v471PreSpeedSignalAgeMs = pendingRequestV471PreSpeedSignalAgeMs[idx];
   v48Mode2Signal = pendingRequestV48Mode2Signal[idx];
   v48Mode2BlockReason = pendingRequestV48Mode2BlockReason[idx];
   v48Mode2OppFlags = pendingRequestV48Mode2OppFlags[idx];
   v48Mode2Velocity1s = pendingRequestV48Mode2Velocity1s[idx];
   v48Mode2WeightFactor = pendingRequestV48Mode2WeightFactor[idx];
   aiJourneyContext = pendingRequestAIJourneyContexts[idx];
}

//+------------------------------------------------------------------+
bool PendingRequestLookup(const ulong positionTicket,
                          const RouterAction expectedAction,
                          double &requestedPrice,
                          double &preEntryScore,
                          string &preEntryBucket,
                          string &preEntryAllow,
                          string &preEntryBlock,
                          string &preEntrySignals,
                          string &v471TapeHealth,
                          double &v471VelocityDecay,
                          long &v471PreSpeedSignalAgeMs,
                          string &v48Mode2Signal,
                          string &v48Mode2BlockReason,
                          int &v48Mode2OppFlags,
                          double &v48Mode2Velocity1s,
                          double &v48Mode2WeightFactor,
                          TheoryAIPreEntryJourneyContextV1 &aiJourneyContext,
                          ulong &matchedRequestTicket,
                          long &decisionMs)
{
   preEntryScore = 0.0;
   preEntryBucket = "";
   preEntryAllow = "";
   preEntryBlock = "";
   preEntrySignals = "";
   v471TapeHealth = "";
   v471VelocityDecay = 0.0;
   v471PreSpeedSignalAgeMs = -1;
   v48Mode2Signal = "";
   v48Mode2BlockReason = "";
   v48Mode2OppFlags = 0;
   v48Mode2Velocity1s = 0.0;
   v48Mode2WeightFactor = 1.0;
   AIPreEntryJourneyResetContext(aiJourneyContext);
   matchedRequestTicket = 0;
   decisionMs = 0;
   if(expectedAction == ActSkip)
      return false;

   // POSITION_IDENTIFIER links the live position to the opening order. The
   // position ticket itself is not guaranteed to equal trade.ResultOrder().
   ulong positionIdentifier = 0;
   if(PositionSelectByTicket(positionTicket))
      positionIdentifier = (ulong)PositionGetInteger(POSITION_IDENTIFIER);

   int fallback = -1;
   int candidateCount = 0;
   for(int i = 0; i < ArraySize(pendingRequestTickets); i++)
   {
      RouterAction action = (RouterAction)pendingRequestActions[i];
      if(action != expectedAction)
         continue;
      candidateCount++;
      if(pendingRequestTickets[i] == positionTicket ||
         (positionIdentifier > 0 && pendingRequestTickets[i] == positionIdentifier))
      {
         matchedRequestTicket = pendingRequestTickets[i];
         decisionMs = pendingRequestDecisionMs[i];
         requestedPrice = pendingRequestPrices[i];
         PendingRequestCopyShadow(i, preEntryScore, preEntryBucket, preEntryAllow, preEntryBlock, preEntrySignals,
                                  v471TapeHealth, v471VelocityDecay, v471PreSpeedSignalAgeMs,
                                  v48Mode2Signal, v48Mode2BlockReason, v48Mode2OppFlags,
                                  v48Mode2Velocity1s, v48Mode2WeightFactor,
                                  aiJourneyContext);
         PendingRequestRemoveIndex(i);
         return true;
      }
      if(fallback < 0)
         fallback = i;
   }

   if(fallback >= 0 && candidateCount == 1)
   {
      matchedRequestTicket = pendingRequestTickets[fallback];
      decisionMs = pendingRequestDecisionMs[fallback];
      requestedPrice = pendingRequestPrices[fallback];
      PendingRequestCopyShadow(fallback, preEntryScore, preEntryBucket, preEntryAllow, preEntryBlock, preEntrySignals,
                               v471TapeHealth, v471VelocityDecay, v471PreSpeedSignalAgeMs,
                               v48Mode2Signal, v48Mode2BlockReason, v48Mode2OppFlags,
                               v48Mode2Velocity1s, v48Mode2WeightFactor,
                               aiJourneyContext);
      PendingRequestRemoveIndex(fallback);
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
datetime ExpiryTime()
{
   if(PendingExpirySeconds <= 0)
      return 0;
   return (datetime)(TimeCurrent() + PendingExpirySeconds);
}

string StopFloorWinningTerm(const double calculatedPoints,
                            const double floorPoints,
                            const string floorTerm)
{
   const double loggedCalculated = NormalizeDouble(calculatedPoints, 1);
   const double loggedFloor = NormalizeDouble(floorPoints, 1);
   if(loggedCalculated == loggedFloor) return "TIE";
   return (loggedCalculated > loggedFloor) ? "CALCULATED" : floorTerm;
}

bool ShouldEmitStopFloor(const ulong ticket,
                         const double calculatedPoints,
                         const double floorPoints,
                         const double appliedPoints,
                         const string winningTerm)
{
   const double loggedCalculated = NormalizeDouble(calculatedPoints, 1);
   const double loggedFloor = NormalizeDouble(floorPoints, 1);
   const double loggedApplied = NormalizeDouble(appliedPoints, 1);
   const int count = ArraySize(stopFloorLogStates);
   for(int i = 0; i < count; i++)
   {
      if(stopFloorLogStates[i].ticket != ticket) continue;
      if(stopFloorLogStates[i].calculatedPoints == loggedCalculated &&
         stopFloorLogStates[i].floorPoints == loggedFloor &&
         stopFloorLogStates[i].appliedPoints == loggedApplied &&
         stopFloorLogStates[i].winningTerm == winningTerm)
         return false;
      stopFloorLogStates[i].calculatedPoints = loggedCalculated;
      stopFloorLogStates[i].floorPoints = loggedFloor;
      stopFloorLogStates[i].appliedPoints = loggedApplied;
      stopFloorLogStates[i].winningTerm = winningTerm;
      return true;
   }
   const int index = ArraySize(stopFloorLogStates);
   ArrayResize(stopFloorLogStates, index + 1);
   stopFloorLogStates[index].ticket = ticket;
   stopFloorLogStates[index].calculatedPoints = loggedCalculated;
   stopFloorLogStates[index].floorPoints = loggedFloor;
   stopFloorLogStates[index].appliedPoints = loggedApplied;
   stopFloorLogStates[index].winningTerm = winningTerm;
   return true;
}

//+------------------------------------------------------------------+
double LegalPrice(const ENUM_ORDER_TYPE type, const MqlTick &t, const double desired)
{
   double minDist = MathMax((double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL),
                            (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL)) * _Point;
   minDist = MathMax(minDist, _Point);
   if(InpUseSplitStopFloor || InpUseTrueStopRiskSizing)
   {
      double serverFloorPoints =
         (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) +
         (InpUseSplitStopFloor ? SERVER_STOP_BUFFER_POINTS : 0.0);
      minDist = MathMax(minDist, serverFloorPoints * _Point);
   }
   double price = desired;
   if(type == ORDER_TYPE_BUY_STOP)  price = MathMax(price, t.ask + minDist);
   if(type == ORDER_TYPE_SELL_STOP) price = MathMin(price, t.bid - minDist);
   if(type == ORDER_TYPE_BUY_LIMIT) price = MathMin(price, t.ask - minDist);
   if(type == ORDER_TYPE_SELL_LIMIT)price = MathMax(price, t.bid + minDist);
   price = NormalizeDouble(price, _Digits);

   if(InpUseSplitStopFloor || InpUseTrueStopRiskSizing)
   {
      double referencePrice = ((type == ORDER_TYPE_BUY_STOP ||
                                type == ORDER_TYPE_SELL_LIMIT)
                               ? t.ask : t.bid);
      double calculatedDistancePoints = MathAbs(desired - referencePrice) / _Point;
      double appliedDistancePoints = MathAbs(price - referencePrice) / _Point;
      double serverFloorPoints =
         (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) +
         (InpUseSplitStopFloor ? SERVER_STOP_BUFFER_POINTS : 0.0);
      double freezeFloorPoints =
         (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
      double floorValuePoints = MathMax(1.0,
                                        MathMax(serverFloorPoints,
                                                freezeFloorPoints));
      string winner = StopFloorWinningTerm(calculatedDistancePoints,
                                            floorValuePoints,
                                            "SYMBOL_STOPS_LEVEL");
      if(ShouldEmitStopFloor(0, calculatedDistancePoints,
                             floorValuePoints, appliedDistancePoints,
                             winner))
         ExecutionAuditWrite("STOP_FLOOR", 0,
         StringFormat("ticket=0 context=%s path=SERVER_PENDING enabled=1 calculated_distance_points=%.1f floor_value_points=%.1f freeze_level_points=%.1f applied_distance_points=%.1f winning_term=%s",
                      EnumToString(type), calculatedDistancePoints,
                      floorValuePoints, freezeFloorPoints,
                      appliedDistancePoints, winner));
   }
   return price;
}

//+------------------------------------------------------------------+
double ServerStopFloorPoints(const double calculatedPoints,
                              const string context,
                              const ulong ticket = 0)
{
   long stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double floorPoints = (double)MathMax(0, (int)stopsLevel);
   bool floorEnabled = (InpUseSplitStopFloor || InpUseTrueStopRiskSizing);
   if(InpUseSplitStopFloor)
      floorPoints += SERVER_STOP_BUFFER_POINTS;

   double appliedPoints = (floorEnabled
                           ? MathMax(calculatedPoints, floorPoints)
                           : calculatedPoints);
   string winner = (!floorEnabled
                     ? "CALCULATED"
                     : StopFloorWinningTerm(calculatedPoints, floorPoints,
                                            "SYMBOL_STOPS_LEVEL"));
   if(floorEnabled && ShouldEmitStopFloor(ticket, calculatedPoints,
                                          floorPoints, appliedPoints,
                                          winner))
      ExecutionAuditWrite("STOP_FLOOR", 0,
         StringFormat("ticket=%llu context=%s path=SERVER enabled=1 calculated_distance_points=%.1f floor_value_points=%.1f applied_distance_points=%.1f winning_term=%s",
                      ticket, context, calculatedPoints, floorPoints,
                      appliedPoints, winner));
   return appliedPoints;
}

void BuildSlTp(const int side,
               const double entry,
               const double slPts,
               const double tpPts,
               const string stopContext,
               double &sl,
               double &tp)
{
   double appliedSlPts = ServerStopFloorPoints(slPts, stopContext);
   if(side > 0)
   {
      sl = NormalizeDouble(entry - appliedSlPts * _Point, _Digits);
      tp = NormalizeDouble(entry + tpPts * _Point, _Digits);
   }
   else
   {
      sl = NormalizeDouble(entry + appliedSlPts * _Point, _Digits);
      tp = NormalizeDouble(entry - tpPts * _Point, _Digits);
   }
}

//+------------------------------------------------------------------+
double NormalizeLots(const double lots)
{
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double v = MathMax(minLot, MathMin(maxLot, lots));
   if(step > 0.0)
      v = MathFloor(v / step) * step;
   return NormalizeDouble(v, 2);
}

//+------------------------------------------------------------------+
double FloorLotsToStep(const double lots, const double step)
{
   if(lots <= 0.0 || step <= 0.0)
      return 0.0;
   return NormalizeDouble(MathFloor((lots / step) + 1e-9) * step, 8);
}

//+------------------------------------------------------------------+
bool ValidateTrailLayerInputs()
{
   const double geometryPairTolerance = 1e-6;
   double expectedMax = internalMinTrailing * internalMultiplier;
   if(MathAbs(internalMaxTrailing - expectedMax) > geometryPairTolerance)
   {
      Print(SAR_TRAIL_GEOMETRY_ERROR,
            " configured_max=", DoubleToString(internalMaxTrailing, 8),
            " expected_max=", DoubleToString(expectedMax, 8),
            " tolerance=", DoubleToString(geometryPairTolerance, 8));
      return false;
   }

   if(internalOrderDistance <= 0.0 || internalMinTrailing <= 0.0 ||
      internalMaxTrailing <= 0.0 || internalMultiplier <= 0.0 ||
      InpReferenceSpreadPts <= 0.0 || InpTrailOuterCapPts <= 0.0 ||
      InpStopBufferPts < 0.0 || InpModifyMinIntervalMs < 0 ||
      InpTrailArmFavPts < 0.0 || InpTrailArmTimeMs < 0 ||
      InpCommissionPts < 0.0 || InpExitSlipReservePts < 0.0 ||
      InpCostLockInPts < 0.0)
   {
      Print("SAR_TRAIL_LAYER_INPUT_INVALID");
      return false;
   }

   if(InpUseTrailLayer && !InpArmOnFavPts && !InpArmOnCostDigested &&
      !InpArmOnTimeMs)
   {
      Print("SAR_TRAIL_LAYER_NO_ARM_ENABLED");
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
bool ValidateAndLogSymbolCalibration()
{
   bool selected = (bool)SymbolInfoInteger(_Symbol, SYMBOL_SELECT);
   bool synchronized = SymbolIsSynchronized(_Symbol);
   long digits = SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   long stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   long freezeLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   double contractSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   double volumeMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double volumeMax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double volumeStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   long fillingMode = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   string accountCurrency = AccountInfoString(ACCOUNT_CURRENCY);

   sarTickSize = tickSize;
   sarTickValue = tickValue;
   sarMinLegalPts = (double)MathMax(stopsLevel, freezeLevel) +
                    InpStopBufferPts;
   sarCostDigestedPts = InpCommissionPts + InpExitSlipReservePts +
                        InpCostLockInPts;

   string details = StringFormat(
      "selected=%d synchronized=%d digits=%I64d point=%.10f tick_size=%.10f tick_value=%.10f stops_level_points=%I64d freeze_level_points=%I64d min_legal_points=%.3f stop_buffer_points=%.3f contract_size=%.8f volume_min=%.8f volume_max=%.8f volume_step=%.8f filling_mode=%I64d account_currency=%s cost_digested_points=%.3f commission_points=%.3f exit_slip_reserve_points=%.3f cost_lock_in_points=%.3f split_stop_floor_enabled=%d true_stop_risk_sizing_enabled=%d",
      selected ? 1 : 0, synchronized ? 1 : 0, digits, point,
      tickSize, tickValue, stopsLevel, freezeLevel, sarMinLegalPts,
      InpStopBufferPts, contractSize,
      volumeMin, volumeMax, volumeStep, fillingMode,
      accountCurrency, sarCostDigestedPts, InpCommissionPts,
      InpExitSlipReservePts, InpCostLockInPts,
      InpUseSplitStopFloor ? 1 : 0,
      InpUseTrueStopRiskSizing ? 1 : 0);
   ExecutionAuditWrite("SYMBOL_CALIBRATION", 0, details);
   Print("SpeedAlert SYMBOL_CALIBRATION ", details);

   return (point > 0.0 && tickSize > 0.0 && volumeMin > 0.0 &&
           volumeMax >= volumeMin && volumeStep > 0.0);
}

//+------------------------------------------------------------------+
void AuditExitReasonConfiguration()
{
   string names[] =
   {
      "FOLMMarketHardCloseComment",
      "FOLMSellMarketEarlyDangerCloseComment",
      "FLXQSellStopPressureDangerCloseComment",
      "StopFlowDisagreeDangerCloseComment",
      "PreSpeedAgainstDefenseCloseComment",
      "RetestFailedEarlyCloseComment",
      "FOLMAfterFollowRetestDangerCloseComment",
      "RetestFailedCloseComment",
      "RetestCollapseHardCloseComment",
      "RetestCollapseCloseComment",
      "NoFollowEarlyCloseComment",
      "NoFollowCloseComment",
      "SpeedProfitExitComment",
      "FOLMPreHardWarnActiveCloseComment",
      "V40PreSpeedExecutionShieldCloseComment",
      "V40FLXQSellStopPressureShieldCloseComment",
      "V40RetestExecutionShieldCloseComment"
   };
   string tags[] =
   {
      FOLMMarketHardCloseComment,
      FOLMSellMarketEarlyDangerCloseComment,
      FLXQSellStopPressureDangerCloseComment,
      StopFlowDisagreeDangerCloseComment,
      PreSpeedAgainstDefenseCloseComment,
      RetestFailedEarlyCloseComment,
      FOLMAfterFollowRetestDangerCloseComment,
      RetestFailedCloseComment,
      RetestCollapseHardCloseComment,
      RetestCollapseCloseComment,
      NoFollowEarlyCloseComment,
      NoFollowCloseComment,
      SpeedProfitExitComment,
      FOLMPreHardWarnActiveCloseComment,
      V40PreSpeedExecutionShieldCloseComment,
      V40FLXQSellStopPressureShieldCloseComment,
      V40RetestExecutionShieldCloseComment
   };

   int issues = 0;
   for(int i = 0; i < ArraySize(tags); i++)
   {
      if(StringLen(tags[i]) <= 0)
      {
         issues++;
         ExecutionAuditWrite("EXIT_REASON_AUDIT", 0,
            "status=MISSING source=" + names[i]);
      }
      for(int j = i + 1; j < ArraySize(tags); j++)
      {
         if(StringLen(tags[i]) > 0 && tags[i] == tags[j])
         {
            issues++;
            ExecutionAuditWrite("EXIT_REASON_AUDIT", 0,
               "status=SHARED tag=" + tags[i] +
               " source_a=" + names[i] + " source_b=" + names[j]);
         }
      }
   }

   ExecutionAuditWrite("EXIT_REASON_AUDIT", 0,
      StringFormat("status=%s configured_reason_families=%d issues=%d frozen_speed_profit_shared_modes=TARGET_EXIT|PREDICTIVE_EXIT central_fallback_comment_inheritance=broker_dependent",
                   (issues == 0 ? "PASS" : "FAIL"),
                   ArraySize(tags), issues));
}

//+------------------------------------------------------------------+
double CalibratedLots(const int side,
                      const double entryPrice,
                      const double stopPrice,
                      const double currentLots)
{
   if(!InpUseTrueStopRiskSizing)
      return currentLots;

   ENUM_ORDER_TYPE orderType = (side > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   double lossPerLot = 0.0;
   ResetLastError();
   if(side == 0 || entryPrice <= 0.0 || stopPrice <= 0.0 ||
      !OrderCalcProfit(orderType, _Symbol, 1.0, entryPrice,
                       stopPrice, lossPerLot))
   {
      ExecutionAuditWrite("LOT_CALIBRATION", side,
         StringFormat("status=FAIL entry=%.10f stop=%.10f error=%d",
                      entryPrice, stopPrice, GetLastError()));
      return 0.0;
   }

   lossPerLot = MathAbs(lossPerLot);
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * MathMax(0.0, InpCalibrationRiskPercent) / 100.0;
   double volumeMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double volumeMax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double volumeStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(lossPerLot <= 0.0 || riskMoney <= 0.0 || volumeMin <= 0.0 ||
      volumeMax < volumeMin || volumeStep <= 0.0)
      return 0.0;

   double rawLots = riskMoney / lossPerLot;
   double flooredLots = FloorLotsToStep(rawLots, volumeStep);
   double lots = MathMax(volumeMin, MathMin(volumeMax, flooredLots));
   lots = NormalizeDouble(lots, 8);
   ExecutionAuditWrite("LOT_CALIBRATION", side,
      StringFormat("status=PASS account_currency=%s risk_percent=%.4f risk_money=%.2f entry=%.10f stop=%.10f loss_per_lot=%.2f raw_lots=%.8f floored_lots=%.8f applied_lots=%.8f volume_min=%.8f volume_max=%.8f volume_step=%.8f",
                   AccountInfoString(ACCOUNT_CURRENCY),
                   InpCalibrationRiskPercent, riskMoney, entryPrice,
                   stopPrice, lossPerLot, rawLots, flooredLots, lots,
                   volumeMin, volumeMax, volumeStep));
   return lots;
}

//+------------------------------------------------------------------+
bool ScenarioCanPlace(const string scenarioKey, const RouterAction action, const DirectionState &s)
{
   if(!ScenarioIndependentPerformance)
   {
      if(MaxOpenPositions > 0 && CountPositions() >= MaxOpenPositions)
      {
         LogCapSkip(action, s, "global_position_cap");
         return false;
      }
      if(MaxPendingOrders > 0 && CountPendings() >= MaxPendingOrders)
      {
         LogCapSkip(action, s, "global_pending_cap");
         return false;
      }
      return true;
   }

   if(MaxOpenPositionsPerScenario > 0 && CountPositionsForScenario(scenarioKey) >= MaxOpenPositionsPerScenario)
   {
      LogCapSkip(action, s, "scenario_position_cap " + scenarioKey);
      return false;
   }

   if(MaxPendingOrdersPerScenario > 0 && CountPendingsForScenario(scenarioKey) >= MaxPendingOrdersPerScenario)
   {
      LogCapSkip(action, s, "scenario_pending_cap " + scenarioKey);
      return false;
   }

   return true;
}

//+------------------------------------------------------------------+
void LogCapSkip(const RouterAction action, const DirectionState &s, const string reason)
{
   datetime now = TimeCurrent();
   if(ScenarioCapLogCooldownSeconds > 0 &&
      reason == lastCapSkipReason &&
      now - lastCapSkipTime < ScenarioCapLogCooldownSeconds)
      return;

   lastCapSkipReason = reason;
   lastCapSkipTime = now;
   LogDecision("SKIP_" + ActionName(action), action, s, reason, 0.0, 0.0, 0.0, 0.0);
}

//+------------------------------------------------------------------+
bool ScenarioCommentMatches(const string comment, const string scenarioKey)
{
   return (StringFind(comment, "SAR:" + scenarioKey + ":") == 0);
}

//+------------------------------------------------------------------+
int CountPositionsForScenario(const string scenarioKey)
{
   int c = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;
      if(ScenarioCommentMatches(PositionGetString(POSITION_COMMENT), scenarioKey))
         c++;
   }
   return c;
}

//+------------------------------------------------------------------+
int CountPendingsForScenario(const string scenarioKey)
{
   int c = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0 || !OrderSelect(ticket))
         continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol || OrderGetInteger(ORDER_MAGIC) != MagicNumber)
         continue;
      if(ScenarioCommentMatches(OrderGetString(ORDER_COMMENT), scenarioKey))
         c++;
   }
   return c;
}

//+------------------------------------------------------------------+
int CountPositions()
{
   int c = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == MagicNumber)
         c++;
   }
   return c;
}

//+------------------------------------------------------------------+
int CountPendings()
{
   int c = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0 || !OrderSelect(ticket))
         continue;
      if(OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == MagicNumber)
         c++;
   }
   return c;
}

//+------------------------------------------------------------------+
void CancelPendingsForScenario(const string scenarioKey, const string reason)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0 || !OrderSelect(ticket))
         continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol || OrderGetInteger(ORDER_MAGIC) != MagicNumber)
         continue;
      if(!ScenarioCommentMatches(OrderGetString(ORDER_COMMENT), scenarioKey))
         continue;
      if(trade.OrderDelete(ticket))
      {
         PendingRequestRemoveTicket(ticket);
         LogInfo("PENDING_CANCEL", reason + " scenario=" + scenarioKey + " ticket=" + (string)ticket);
      }
   }
}

//+------------------------------------------------------------------+
void CancelPendings(const string reason)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0 || !OrderSelect(ticket))
         continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol || OrderGetInteger(ORDER_MAGIC) != MagicNumber)
         continue;
      if(trade.OrderDelete(ticket))
      {
         PendingRequestRemoveTicket(ticket);
         LogInfo("PENDING_CANCEL", reason + " ticket=" + (string)ticket);
      }
   }
}

//+------------------------------------------------------------------+
void ManagePendingExpiry()
{
   if(PendingExpirySeconds <= 0)
      return;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0 || !OrderSelect(ticket))
         continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol || OrderGetInteger(ORDER_MAGIC) != MagicNumber)
         continue;
      datetime setupTime = (datetime)OrderGetInteger(ORDER_TIME_SETUP);
      if(TimeCurrent() - setupTime >= PendingExpirySeconds && trade.OrderDelete(ticket))
      {
         PendingRequestRemoveTicket(ticket);
         LogInfo("PENDING_EXPIRED", "ticket=" + (string)ticket);
      }
   }
}

//+------------------------------------------------------------------+
int TrackerIndex(const ulong ticket)
{
   for(int i = 0; i < ArraySize(trackedTickets); i++)
      if(trackedTickets[i] == ticket)
         return i;
   return -1;
}

//+------------------------------------------------------------------+
bool PositionTrackAlreadyLogged(const ulong ticket)
{
   for(int i = 0; i < ArraySize(positionTrackLoggedTickets); i++)
      if(positionTrackLoggedTickets[i] == ticket)
         return true;
   return false;
}

//+------------------------------------------------------------------+
int ClosingTicketIndex(const ulong ticket)
{
   for(int i = 0; i < ArraySize(closingTickets); i++)
      if(closingTickets[i] == ticket)
         return i;
   return -1;
}

//+------------------------------------------------------------------+
bool IsTicketClosing(const ulong ticket)
{
   return (ticket != 0 && ClosingTicketIndex(ticket) >= 0);
}

//+------------------------------------------------------------------+
int CloseLoggedTicketIndex(const ulong ticket)
{
   for(int i = 0; i < ArraySize(closeLoggedTickets); i++)
      if(closeLoggedTickets[i] == ticket)
         return i;
   return -1;
}

//+------------------------------------------------------------------+
void PruneCloseLoggedTickets()
{
   long nowMs = GetTickMs();
   long keepMs = (CloseDuplicateMemoryMs > 0 ? CloseDuplicateMemoryMs : 10000);
   for(int i = ArraySize(closeLoggedTickets) - 1; i >= 0; i--)
      if(nowMs - closeLoggedTicketMs[i] > keepMs)
      {
         int n = ArraySize(closeLoggedTickets);
         for(int j = i; j < n - 1; j++)
         {
            closeLoggedTickets[j] = closeLoggedTickets[j + 1];
            closeLoggedTicketMs[j] = closeLoggedTicketMs[j + 1];
            closeLoggedTicketEvents[j] = closeLoggedTicketEvents[j + 1];
         }
         ArrayResize(closeLoggedTickets, n - 1);
         ArrayResize(closeLoggedTicketMs, n - 1);
         ArrayResize(closeLoggedTicketEvents, n - 1);
      }
}

//+------------------------------------------------------------------+
bool IsCloseLoggedRecently(const ulong ticket)
{
   if(ticket == 0)
      return false;
   PruneCloseLoggedTickets();
   return (CloseLoggedTicketIndex(ticket) >= 0);
}

//+------------------------------------------------------------------+
void MarkCloseLogged(const ulong ticket, const string eventName)
{
   if(ticket == 0)
      return;

   PruneCloseLoggedTickets();
   int idx = CloseLoggedTicketIndex(ticket);
   if(idx >= 0)
   {
      closeLoggedTicketEvents[idx] = eventName;
      closeLoggedTicketMs[idx] = GetTickMs();
      return;
   }

   int n = ArraySize(closeLoggedTickets);
   ArrayResize(closeLoggedTickets, n + 1);
   ArrayResize(closeLoggedTicketMs, n + 1);
   ArrayResize(closeLoggedTicketEvents, n + 1);
   closeLoggedTickets[n] = ticket;
   closeLoggedTicketMs[n] = GetTickMs();
   closeLoggedTicketEvents[n] = eventName;
}

//+------------------------------------------------------------------+
ulong TicketFromText(const string text)
{
   int p = StringFind(text, "ticket=");
   if(p < 0)
      return 0;

   p += 7;
   string digits = "";
   int len = StringLen(text);
   while(p < len)
   {
      ushort ch = StringGetCharacter(text, p);
      if(ch < 48 || ch > 57)
         break;
      digits += StringSubstr(text, p, 1);
      p++;
   }

   if(StringLen(digits) <= 0)
      return 0;
   return (ulong)StringToInteger(digits);
}

//+------------------------------------------------------------------+
bool IsSuccessfulCloseLogEvent(const string eventName)
{
   if(eventName == "SPEED_PROFIT_EXIT" ||
      eventName == "RETEST_FAILED_CLOSE" ||
      eventName == "PRE_SPEED_AGAINST_DEFENSE_RETRY_RESOLVED_CLOSE")
      return true;
   if(StringFind(eventName, "_CLOSE") < 0)
      return false;
   if(StringFind(eventName, "FAILED") >= 0 ||
      StringFind(eventName, "PAUSED") >= 0 ||
      StringFind(eventName, "SKIP") >= 0 ||
      StringFind(eventName, "POSITION_GONE") >= 0)
      return false;
   return true;
}

//+------------------------------------------------------------------+
bool IsDefensiveCloseLogEvent(const string eventName)
{
   if(!IsSuccessfulCloseLogEvent(eventName))
      return false;
   return (eventName != "SPEED_PROFIT_EXIT");
}

//+------------------------------------------------------------------+
bool DefensiveLockoutActive()
{
   if(!UseDefensiveCloseLockout)
      return false;
   return (defensiveLockoutUntilMs > GetTickMs());
}

//+------------------------------------------------------------------+
void LogDefensiveLockoutInfo(const string eventName, const string reason)
{
   DirectionState s;
   ResetState(s);
   s.scenario = "INFO";
   s.labels = reason;
   LogDecision(eventName, ActSkip, s, reason, 0.0, 0.0, 0.0, 0.0);
}

//+------------------------------------------------------------------+
void UpdateDefensiveLockoutAfterClose(const string eventName, const string reason)
{
   if(!UseDefensiveCloseLockout)
      return;

   long nowMs = GetTickMs();
   if(eventName == "SPEED_PROFIT_EXIT")
   {
      if(defensiveCloseStreak > 0 || defensiveLockoutUntilMs > nowMs)
      {
         defensiveCloseStreak = 0;
         defensiveLockoutUntilMs = 0;
         LogDefensiveLockoutInfo("DEFENSIVE_LOCKOUT_RESET",
                                 "speed_profit_exit streak_reset=true close_event=" + eventName);
      }
      return;
   }

   if(!IsDefensiveCloseLogEvent(eventName))
      return;

   defensiveCloseStreak++;
   int triggerCount = (DefensiveLockoutCloseCount > 1 ? DefensiveLockoutCloseCount : 1);
   if(defensiveCloseStreak < triggerCount)
      return;

   long lockoutMs = (long)(DefensiveLockoutSeconds > 1 ? DefensiveLockoutSeconds : 1) * 1000;
   long newUntilMs = nowMs + lockoutMs;
   if(newUntilMs > defensiveLockoutUntilMs)
      defensiveLockoutUntilMs = newUntilMs;
   long remainingMs = defensiveLockoutUntilMs - nowMs;
   if(remainingMs < 0)
      remainingMs = 0;
   LogDefensiveLockoutInfo("DEFENSIVE_LOCKOUT_ARMED",
                           "defensive_close_streak=" + (string)defensiveCloseStreak +
                           " trigger_count=" + (string)triggerCount +
                           " lockout_seconds=" + (string)DefensiveLockoutSeconds +
                           " remaining_ms=" + (string)remainingMs +
                           " close_event=" + eventName +
                           " close_reason=" + reason);
   if(DefensiveLockoutCancelPendings)
      CancelPendings("defensive_lockout_armed");
   defensiveCloseStreak = 0;
}

//+------------------------------------------------------------------+
bool SkipEntryForDefensiveLockout()
{
   if(!DefensiveLockoutActive())
      return false;

   long nowMs = GetTickMs();
      long cooldownMs = (long)(DefensiveLockoutLogCooldownSeconds > 1 ? DefensiveLockoutLogCooldownSeconds : 1) * 1000;
   if(defensiveLockoutLastLogMs <= 0 || nowMs - defensiveLockoutLastLogMs >= cooldownMs)
   {
      defensiveLockoutLastLogMs = nowMs;
      long remainingMs = defensiveLockoutUntilMs - nowMs;
      if(remainingMs < 0)
         remainingMs = 0;
      LogDefensiveLockoutInfo("DEFENSIVE_LOCKOUT_SKIP",
                              "remaining_ms=" + (string)remainingMs +
                              " streak=" + (string)defensiveCloseStreak +
                              " speed_dir=" + (string)speedDir +
                              " speed_points=" + DoubleToString(speedPoints, 1));
   }

   speedActive = false;
   return true;
}

//+------------------------------------------------------------------+
void MarkTicketClosing(const ulong ticket, const string eventName)
{
   if(ticket == 0)
      return;

   int idx = ClosingTicketIndex(ticket);
   if(idx >= 0)
   {
      closingTicketEvents[idx] = eventName;
      closingTicketMs[idx] = GetTickMs();
      return;
   }

   int n = ArraySize(closingTickets);
   ArrayResize(closingTickets, n + 1);
   ArrayResize(closingTicketMs, n + 1);
   ArrayResize(closingTicketEvents, n + 1);
   closingTickets[n] = ticket;
   closingTicketMs[n] = GetTickMs();
   closingTicketEvents[n] = eventName;
}

//+------------------------------------------------------------------+
void ClosingTicketRemoveIndex(const int idx)
{
   int n = ArraySize(closingTickets);
   if(idx < 0 || idx >= n)
      return;

   for(int i = idx; i < n - 1; i++)
   {
      closingTickets[i] = closingTickets[i + 1];
      closingTicketMs[i] = closingTicketMs[i + 1];
      closingTicketEvents[i] = closingTicketEvents[i + 1];
   }
   ArrayResize(closingTickets, n - 1);
   ArrayResize(closingTicketMs, n - 1);
   ArrayResize(closingTicketEvents, n - 1);
}

//+------------------------------------------------------------------+
void ClearClosingTicket(const ulong ticket)
{
   ClosingTicketRemoveIndex(ClosingTicketIndex(ticket));
}

//+------------------------------------------------------------------+
void PositionTrackMarkLogged(const ulong ticket)
{
   if(ticket == 0 || PositionTrackAlreadyLogged(ticket))
      return;

   int n = ArraySize(positionTrackLoggedTickets);
   ArrayResize(positionTrackLoggedTickets, n + 1);
   positionTrackLoggedTickets[n] = ticket;
}

//+------------------------------------------------------------------+
double TrackedLastKnownFav(const int idx)
{
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return 0.0;
   if(trackedLastFavs[idx] != 0.0)
      return trackedLastFavs[idx];
   if(trackedMaes[idx] != 0.0)
      return trackedMaes[idx];
   return trackedMfes[idx];
}

//+------------------------------------------------------------------+
void TrackerSetLastKnownFav(const int idx, const double fav)
{
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return;
   trackedLastFavs[idx] = fav;
   trackedLastFavMs[idx] = GetTickMs();
}

//+------------------------------------------------------------------+
int TrackerAdd(const ulong ticket, const long entryMs, const double entry, const int side, const string labels)
{
   int n = ArraySize(trackedTickets);
   ArrayResize(trackedTickets, n + 1);
   ArrayResize(trackedEntryMs, n + 1);
   ArrayResize(trackedEntries, n + 1);
   ArrayResize(trackedSides, n + 1);
   ArrayResize(trackedMfes, n + 1);
   ArrayResize(trackedMaes, n + 1);
   ArrayResize(trackedHit21s, n + 1);
   ArrayResize(trackedHit37s, n + 1);
   ArrayResize(trackedRetestHelds, n + 1);
   ArrayResize(trackedRetestFaileds, n + 1);
   ArrayResize(trackedFirst10sMfes, n + 1);
   ArrayResize(trackedTickCounts, n + 1);
   ArrayResize(trackedMaxSingleTickAdversePts, n + 1);
   ArrayResize(trackedLastTickDeltaPts, n + 1);
   ArrayResize(trackedEntryTickJumpWithTrades, n + 1);
   ArrayResize(trackedEntryTickJumpAgainstTrades, n + 1);
   ArrayResize(trackedFirst500msMaxAdverseJumpPts, n + 1);
   ArrayResize(trackedFirst1sMaxAdverseJumpPts, n + 1);
   ArrayResize(trackedFirst2sMaxAdverseJumpPts, n + 1);
   ArrayResize(trackedFirst250msMaxAdverseJumpPts, n + 1);
   ArrayResize(trackedFirst750msMaxAdverseJumpPts, n + 1);
   ArrayResize(trackedV44First1sShadowFired, n + 1);
   ArrayResize(trackedV44First1sShadowMs, n + 1);
   ArrayResize(trackedV44First1sShadowFav, n + 1);
   ArrayResize(trackedV44First2sShadowFired, n + 1);
   ArrayResize(trackedV44First2sShadowMs, n + 1);
   ArrayResize(trackedV44First2sShadowFav, n + 1);
   ArrayResize(trackedV451LowJFirst1sFired, n + 1);
   ArrayResize(trackedV451LowJFirst1sMs, n + 1);
   ArrayResize(trackedV451LowJFirst1sFav, n + 1);
   ArrayResize(trackedV451LowJFirst2sFired, n + 1);
   ArrayResize(trackedV451LowJFirst2sMs, n + 1);
   ArrayResize(trackedV451LowJFirst2sFav, n + 1);
   ArrayResize(trackedV451FlowOppSourceTiming, n + 1);
   ArrayResize(trackedV451FlowOppSourceMs, n + 1);
   ArrayResize(trackedV451FlowOppSourceFav, n + 1);
   ArrayResize(trackedV46LowDeadShadowFired, n + 1);
   ArrayResize(trackedV46LowDeadShadowMs, n + 1);
   ArrayResize(trackedV46LowDeadShadowFav, n + 1);
   ArrayResize(trackedV46LowDeadShadowMfe, n + 1);
   ArrayResize(trackedV46LowDeadShadowMaxFav1To3, n + 1);
   ArrayResize(trackedV46LowDeadShadowReason, n + 1);
   ArrayResize(trackedPreWarn15JumpAgainstTrades, n + 1);
   ArrayResize(trackedPreWarn18JumpAgainstTrades, n + 1);
   ArrayResize(trackedPreWarn21JumpAgainstTrades, n + 1);
   ArrayResize(trackedPreWarn24JumpAgainstTrades, n + 1);
   ArrayResize(trackedLastQuoteGapMs, n + 1);
   ArrayResize(trackedLastTelemetryTickMs, n + 1);
   ArrayResize(trackedFOLMWarn15Ms, n + 1);
   ArrayResize(trackedFOLMWarn18Ms, n + 1);
   ArrayResize(trackedFOLMWarn21Ms, n + 1);
   ArrayResize(trackedFOLMWarn24Ms, n + 1);
   ArrayResize(trackedFOLMWarn24Ticks, n + 1);
   ArrayResize(trackedFavAt250ms, n + 1);
   ArrayResize(trackedFavAt500ms, n + 1);
   ArrayResize(trackedFavAt1s, n + 1);
   ArrayResize(trackedFavAt2s, n + 1);
   ArrayResize(trackedFavAt3s, n + 1);
   ArrayResize(trackedFavAt100ms, n + 1);
   ArrayResize(trackedFavAt750ms, n + 1);
   ArrayResize(trackedFavAt1500ms, n + 1);
   ArrayResize(trackedAliveAt100ms, n + 1);
   ArrayResize(trackedAliveAt250ms, n + 1);
   ArrayResize(trackedAliveAt500ms, n + 1);
   ArrayResize(trackedAliveAt750ms, n + 1);
   ArrayResize(trackedAliveAt1s, n + 1);
   ArrayResize(trackedAliveAt1500ms, n + 1);
   ArrayResize(trackedAliveAt2s, n + 1);
   ArrayResize(trackedAliveAt3s, n + 1);
   ArrayResize(trackedSampleMsAt100ms, n + 1);
   ArrayResize(trackedSampleMsAt250ms, n + 1);
   ArrayResize(trackedSampleMsAt500ms, n + 1);
   ArrayResize(trackedSampleMsAt750ms, n + 1);
   ArrayResize(trackedSampleMsAt1s, n + 1);
   ArrayResize(trackedSampleMsAt1500ms, n + 1);
   ArrayResize(trackedSampleMsAt2s, n + 1);
   ArrayResize(trackedSampleMsAt3s, n + 1);
   ArrayResize(trackedTicksAt100ms, n + 1);
   ArrayResize(trackedTicksAt250ms, n + 1);
   ArrayResize(trackedTicksAt500ms, n + 1);
   ArrayResize(trackedTicksAt750ms, n + 1);
   ArrayResize(trackedTicksAt1s, n + 1);
   ArrayResize(trackedTicksAt1500ms, n + 1);
   ArrayResize(trackedTicksAt2s, n + 1);
   ArrayResize(trackedTicksAt3s, n + 1);
   ArrayResize(trackedTimeToFirstProfitMs, n + 1);
   ArrayResize(trackedTimeToMfe10Ms, n + 1);
   ArrayResize(trackedTimeToMfe20Ms, n + 1);
   ArrayResize(trackedTimeToMfe40Ms, n + 1);
   ArrayResize(trackedTimeToSpeedMs, n + 1);
   ArrayResize(trackedFirstProfitSeen, n + 1);
   ArrayResize(trackedPeakAfterFirstProfit, n + 1);
   ArrayResize(trackedMaxPullbackAfterFirstProfit, n + 1);
   ArrayResize(trackedV461LowDetectSpread, n + 1);
   ArrayResize(trackedV461LowDetectOrderflowState, n + 1);
   ArrayResize(trackedV461LowDetectPressureState, n + 1);
   ArrayResize(trackedV461OppAtLowMfe, n + 1);
   ArrayResize(trackedV461OppAtLowMae, n + 1);
   ArrayResize(trackedV461OppAtLowWouldSpeed, n + 1);
   ArrayResize(trackedV461OppAtLowWouldHardLose, n + 1);
   ArrayResize(trackedPreEntryHighShadowScores, n + 1);
   ArrayResize(trackedPreEntryHighShadowBuckets, n + 1);
   ArrayResize(trackedPreEntryHighWouldAllows, n + 1);
   ArrayResize(trackedPreEntryHighWouldBlocks, n + 1);
   ArrayResize(trackedPreEntryHighSignals, n + 1);
   ArrayResize(trackedV471TickPath, n + 1);
   ArrayResize(trackedV471PreEntryTapeHealth, n + 1);
   ArrayResize(trackedV471PreEntryVelocityDecay, n + 1);
   ArrayResize(trackedV471PreSpeedSignalAgeMs, n + 1);
   ArrayResize(trackedV48Mode2Signal, n + 1);
   ArrayResize(trackedV48Mode2BlockReason, n + 1);
   ArrayResize(trackedV48Mode2OppFlags, n + 1);
   ArrayResize(trackedV48Mode2Velocity1s, n + 1);
   ArrayResize(trackedV48Mode2WeightFactor, n + 1);
   ArrayResize(trackedUrgentCloseStartMs, n + 1);
   ArrayResize(trackedFOLMPreHardWarningMasks, n + 1);
   ArrayResize(trackedRetestPreFailWarningMasks, n + 1);
   ArrayResize(trackedRetestFailStartMs, n + 1);
   ArrayResize(trackedRetestFailStartFavs, n + 1);
   ArrayResize(trackedRetestCollapseStartMs, n + 1);
   ArrayResize(trackedRetestCollapseTicks, n + 1);
   ArrayResize(trackedLastFavs, n + 1);
   ArrayResize(trackedLastFavMs, n + 1);
   ArrayResize(trackedLabels, n + 1);
   ArrayResize(trackedSpeedExitPendings, n + 1);
   ArrayResize(trackedSpeedExitLastTryMs, n + 1);
   ArrayResize(trackedSpeedExitRetryCounts, n + 1);
   ArrayResize(trackedSpeedExitLimitLogged, n + 1);
   ArrayResize(trackedSpeedExitUnsafeLogged, n + 1);
   ArrayResize(trackedHardFloorUrgentClose, n + 1);
   ArrayResize(trackedHardFloorLastLogMs, n + 1);
   ArrayResize(trackedHardFloorAttempts, n + 1);
   ArrayResize(trackedRetestCollapseUrgentClose, n + 1);
   ArrayResize(trackedRetestCollapseLastLogMs, n + 1);
   ArrayResize(trackedRetestCollapseAttempts, n + 1);
   ArrayResize(trackedPreSpeedDefenseUrgentClose, n + 1);
   ArrayResize(trackedPreSpeedDefenseLastLogMs, n + 1);
   ArrayResize(trackedPreSpeedDefenseAttempts, n + 1);
   ArrayResize(trackedRetestPauseLastLogMs, n + 1);

   trackedTickets[n] = ticket;
   trackedEntryMs[n] = entryMs;
   trackedEntries[n] = entry;
   trackedSides[n] = side;
   trackedMfes[n] = 0.0;
   trackedMaes[n] = 0.0;
   trackedHit21s[n] = false;
   trackedHit37s[n] = false;
   trackedRetestHelds[n] = false;
   trackedRetestFaileds[n] = false;
   trackedFirst10sMfes[n] = 0.0;
   trackedTickCounts[n] = 0;
   trackedMaxSingleTickAdversePts[n] = 0.0;
   trackedLastTickDeltaPts[n] = 0.0;
   trackedEntryTickJumpWithTrades[n] = -1;
   trackedEntryTickJumpAgainstTrades[n] = -1;
   trackedFirst500msMaxAdverseJumpPts[n] = 0.0;
   trackedFirst1sMaxAdverseJumpPts[n] = 0.0;
   trackedFirst2sMaxAdverseJumpPts[n] = 0.0;
   trackedFirst250msMaxAdverseJumpPts[n] = 0.0;
   trackedFirst750msMaxAdverseJumpPts[n] = 0.0;
   trackedV44First1sShadowFired[n] = false;
   trackedV44First1sShadowMs[n] = 0;
   trackedV44First1sShadowFav[n] = 0.0;
   trackedV44First2sShadowFired[n] = false;
   trackedV44First2sShadowMs[n] = 0;
   trackedV44First2sShadowFav[n] = 0.0;
   trackedV451LowJFirst1sFired[n] = false;
   trackedV451LowJFirst1sMs[n] = 0;
   trackedV451LowJFirst1sFav[n] = 0.0;
   trackedV451LowJFirst2sFired[n] = false;
   trackedV451LowJFirst2sMs[n] = 0;
   trackedV451LowJFirst2sFav[n] = 0.0;
   trackedV451FlowOppSourceTiming[n] = "";
   trackedV451FlowOppSourceMs[n] = 0;
   trackedV451FlowOppSourceFav[n] = 0.0;
   trackedV46LowDeadShadowFired[n] = false;
   trackedV46LowDeadShadowMs[n] = 0;
   trackedV46LowDeadShadowFav[n] = 0.0;
   trackedV46LowDeadShadowMfe[n] = 0.0;
   trackedV46LowDeadShadowMaxFav1To3[n] = 0.0;
   trackedV46LowDeadShadowReason[n] = "";
   trackedPreWarn15JumpAgainstTrades[n] = -1;
   trackedPreWarn18JumpAgainstTrades[n] = -1;
   trackedPreWarn21JumpAgainstTrades[n] = -1;
   trackedPreWarn24JumpAgainstTrades[n] = -1;
   trackedLastQuoteGapMs[n] = 0;
   trackedLastTelemetryTickMs[n] = 0;
   trackedFOLMWarn15Ms[n] = 0;
   trackedFOLMWarn18Ms[n] = 0;
   trackedFOLMWarn21Ms[n] = 0;
   trackedFOLMWarn24Ms[n] = 0;
   trackedFOLMWarn24Ticks[n] = 0;
   trackedFavAt250ms[n] = ROUTER_BIG_VALUE;
   trackedFavAt500ms[n] = ROUTER_BIG_VALUE;
   trackedFavAt1s[n] = ROUTER_BIG_VALUE;
   trackedFavAt2s[n] = ROUTER_BIG_VALUE;
   trackedFavAt3s[n] = ROUTER_BIG_VALUE;
   trackedFavAt100ms[n] = ROUTER_BIG_VALUE;
   trackedFavAt750ms[n] = ROUTER_BIG_VALUE;
   trackedFavAt1500ms[n] = ROUTER_BIG_VALUE;
   trackedAliveAt100ms[n] = false;
   trackedAliveAt250ms[n] = false;
   trackedAliveAt500ms[n] = false;
   trackedAliveAt750ms[n] = false;
   trackedAliveAt1s[n] = false;
   trackedAliveAt1500ms[n] = false;
   trackedAliveAt2s[n] = false;
   trackedAliveAt3s[n] = false;
   trackedSampleMsAt100ms[n] = 0;
   trackedSampleMsAt250ms[n] = 0;
   trackedSampleMsAt500ms[n] = 0;
   trackedSampleMsAt750ms[n] = 0;
   trackedSampleMsAt1s[n] = 0;
   trackedSampleMsAt1500ms[n] = 0;
   trackedSampleMsAt2s[n] = 0;
   trackedSampleMsAt3s[n] = 0;
   trackedTicksAt100ms[n] = 0;
   trackedTicksAt250ms[n] = 0;
   trackedTicksAt500ms[n] = 0;
   trackedTicksAt750ms[n] = 0;
   trackedTicksAt1s[n] = 0;
   trackedTicksAt1500ms[n] = 0;
   trackedTicksAt2s[n] = 0;
   trackedTicksAt3s[n] = 0;
   trackedTimeToFirstProfitMs[n] = 0;
   trackedTimeToMfe10Ms[n] = 0;
   trackedTimeToMfe20Ms[n] = 0;
   trackedTimeToMfe40Ms[n] = 0;
   trackedTimeToSpeedMs[n] = 0;
   trackedFirstProfitSeen[n] = false;
   trackedPeakAfterFirstProfit[n] = 0.0;
   trackedMaxPullbackAfterFirstProfit[n] = 0.0;
   trackedV461LowDetectSpread[n] = 0.0;
   trackedV461LowDetectOrderflowState[n] = "";
   trackedV461LowDetectPressureState[n] = "";
   trackedV461OppAtLowMfe[n] = 0.0;
   trackedV461OppAtLowMae[n] = 0.0;
   trackedV461OppAtLowWouldSpeed[n] = false;
   trackedV461OppAtLowWouldHardLose[n] = false;
   trackedPreEntryHighShadowScores[n] = 0.0;
   trackedPreEntryHighShadowBuckets[n] = "";
   trackedPreEntryHighWouldAllows[n] = "";
   trackedPreEntryHighWouldBlocks[n] = "";
   trackedPreEntryHighSignals[n] = "";
   trackedV471TickPath[n] = "";
   trackedV471PreEntryTapeHealth[n] = "";
   trackedV471PreEntryVelocityDecay[n] = 0.0;
   trackedV471PreSpeedSignalAgeMs[n] = -1;
   trackedV48Mode2Signal[n] = "";
   trackedV48Mode2BlockReason[n] = "";
   trackedV48Mode2OppFlags[n] = 0;
   trackedV48Mode2Velocity1s[n] = 0.0;
   trackedV48Mode2WeightFactor[n] = 1.0;
   trackedUrgentCloseStartMs[n] = 0;
   trackedFOLMPreHardWarningMasks[n] = 0;
   trackedRetestPreFailWarningMasks[n] = 0;
   trackedRetestFailStartMs[n] = 0;
   trackedRetestFailStartFavs[n] = 0.0;
   trackedRetestCollapseStartMs[n] = 0;
   trackedRetestCollapseTicks[n] = 0;
   trackedLastFavs[n] = 0.0;
   trackedLastFavMs[n] = entryMs;
   trackedLabels[n] = labels;
   TrackV451FlowOppSource(n, 0, 0.0);
   trackedSpeedExitPendings[n] = false;
   trackedSpeedExitLastTryMs[n] = 0;
   trackedSpeedExitRetryCounts[n] = 0;
   trackedSpeedExitLimitLogged[n] = false;
   trackedSpeedExitUnsafeLogged[n] = false;
   trackedHardFloorUrgentClose[n] = false;
   trackedHardFloorLastLogMs[n] = 0;
   trackedHardFloorAttempts[n] = 0;
   trackedRetestCollapseUrgentClose[n] = false;
   trackedRetestCollapseLastLogMs[n] = 0;
   trackedRetestCollapseAttempts[n] = 0;
   trackedPreSpeedDefenseUrgentClose[n] = false;
   trackedPreSpeedDefenseLastLogMs[n] = 0;
   trackedPreSpeedDefenseAttempts[n] = 0;
   trackedRetestPauseLastLogMs[n] = 0;
   if(UseV43EarlyJumpTelemetry)
   {
      double entryAdverseDeltaPts = 0.0;
      bool hasEntryDelta = LatestAdverseTickDeltaPoints(side, entryAdverseDeltaPts);
      BuildJumpDirectionFlags(hasEntryDelta, entryAdverseDeltaPts,
                              trackedEntryTickJumpWithTrades[n],
                              trackedEntryTickJumpAgainstTrades[n]);
   }
   return n;
}

//+------------------------------------------------------------------+
void TrackerRemoveIndex(const int idx)
{
   int n = ArraySize(trackedTickets);
   if(idx < 0 || idx >= n)
      return;

   for(int i = idx; i < n - 1; i++)
   {
      trackedTickets[i] = trackedTickets[i + 1];
      trackedEntryMs[i] = trackedEntryMs[i + 1];
      trackedEntries[i] = trackedEntries[i + 1];
      trackedSides[i] = trackedSides[i + 1];
      trackedMfes[i] = trackedMfes[i + 1];
      trackedMaes[i] = trackedMaes[i + 1];
      trackedHit21s[i] = trackedHit21s[i + 1];
      trackedHit37s[i] = trackedHit37s[i + 1];
      trackedRetestHelds[i] = trackedRetestHelds[i + 1];
      trackedRetestFaileds[i] = trackedRetestFaileds[i + 1];
      trackedFirst10sMfes[i] = trackedFirst10sMfes[i + 1];
      trackedTickCounts[i] = trackedTickCounts[i + 1];
      trackedMaxSingleTickAdversePts[i] = trackedMaxSingleTickAdversePts[i + 1];
      trackedLastTickDeltaPts[i] = trackedLastTickDeltaPts[i + 1];
      trackedEntryTickJumpWithTrades[i] = trackedEntryTickJumpWithTrades[i + 1];
      trackedEntryTickJumpAgainstTrades[i] = trackedEntryTickJumpAgainstTrades[i + 1];
      trackedFirst500msMaxAdverseJumpPts[i] = trackedFirst500msMaxAdverseJumpPts[i + 1];
      trackedFirst1sMaxAdverseJumpPts[i] = trackedFirst1sMaxAdverseJumpPts[i + 1];
      trackedFirst2sMaxAdverseJumpPts[i] = trackedFirst2sMaxAdverseJumpPts[i + 1];
      trackedFirst250msMaxAdverseJumpPts[i] = trackedFirst250msMaxAdverseJumpPts[i + 1];
      trackedFirst750msMaxAdverseJumpPts[i] = trackedFirst750msMaxAdverseJumpPts[i + 1];
      trackedV44First1sShadowFired[i] = trackedV44First1sShadowFired[i + 1];
      trackedV44First1sShadowMs[i] = trackedV44First1sShadowMs[i + 1];
      trackedV44First1sShadowFav[i] = trackedV44First1sShadowFav[i + 1];
      trackedV44First2sShadowFired[i] = trackedV44First2sShadowFired[i + 1];
      trackedV44First2sShadowMs[i] = trackedV44First2sShadowMs[i + 1];
      trackedV44First2sShadowFav[i] = trackedV44First2sShadowFav[i + 1];
      trackedV451LowJFirst1sFired[i] = trackedV451LowJFirst1sFired[i + 1];
      trackedV451LowJFirst1sMs[i] = trackedV451LowJFirst1sMs[i + 1];
      trackedV451LowJFirst1sFav[i] = trackedV451LowJFirst1sFav[i + 1];
      trackedV451LowJFirst2sFired[i] = trackedV451LowJFirst2sFired[i + 1];
      trackedV451LowJFirst2sMs[i] = trackedV451LowJFirst2sMs[i + 1];
      trackedV451LowJFirst2sFav[i] = trackedV451LowJFirst2sFav[i + 1];
      trackedV451FlowOppSourceTiming[i] = trackedV451FlowOppSourceTiming[i + 1];
      trackedV451FlowOppSourceMs[i] = trackedV451FlowOppSourceMs[i + 1];
      trackedV451FlowOppSourceFav[i] = trackedV451FlowOppSourceFav[i + 1];
      trackedV46LowDeadShadowFired[i] = trackedV46LowDeadShadowFired[i + 1];
      trackedV46LowDeadShadowMs[i] = trackedV46LowDeadShadowMs[i + 1];
      trackedV46LowDeadShadowFav[i] = trackedV46LowDeadShadowFav[i + 1];
      trackedV46LowDeadShadowMfe[i] = trackedV46LowDeadShadowMfe[i + 1];
      trackedV46LowDeadShadowMaxFav1To3[i] = trackedV46LowDeadShadowMaxFav1To3[i + 1];
      trackedV46LowDeadShadowReason[i] = trackedV46LowDeadShadowReason[i + 1];
      trackedPreWarn15JumpAgainstTrades[i] = trackedPreWarn15JumpAgainstTrades[i + 1];
      trackedPreWarn18JumpAgainstTrades[i] = trackedPreWarn18JumpAgainstTrades[i + 1];
      trackedPreWarn21JumpAgainstTrades[i] = trackedPreWarn21JumpAgainstTrades[i + 1];
      trackedPreWarn24JumpAgainstTrades[i] = trackedPreWarn24JumpAgainstTrades[i + 1];
      trackedLastQuoteGapMs[i] = trackedLastQuoteGapMs[i + 1];
      trackedLastTelemetryTickMs[i] = trackedLastTelemetryTickMs[i + 1];
      trackedFOLMWarn15Ms[i] = trackedFOLMWarn15Ms[i + 1];
      trackedFOLMWarn18Ms[i] = trackedFOLMWarn18Ms[i + 1];
      trackedFOLMWarn21Ms[i] = trackedFOLMWarn21Ms[i + 1];
      trackedFOLMWarn24Ms[i] = trackedFOLMWarn24Ms[i + 1];
      trackedFOLMWarn24Ticks[i] = trackedFOLMWarn24Ticks[i + 1];
      trackedFavAt250ms[i] = trackedFavAt250ms[i + 1];
      trackedFavAt500ms[i] = trackedFavAt500ms[i + 1];
      trackedFavAt1s[i] = trackedFavAt1s[i + 1];
      trackedFavAt2s[i] = trackedFavAt2s[i + 1];
      trackedFavAt3s[i] = trackedFavAt3s[i + 1];
      trackedFavAt100ms[i] = trackedFavAt100ms[i + 1];
      trackedFavAt750ms[i] = trackedFavAt750ms[i + 1];
      trackedFavAt1500ms[i] = trackedFavAt1500ms[i + 1];
      trackedAliveAt100ms[i] = trackedAliveAt100ms[i + 1];
      trackedAliveAt250ms[i] = trackedAliveAt250ms[i + 1];
      trackedAliveAt500ms[i] = trackedAliveAt500ms[i + 1];
      trackedAliveAt750ms[i] = trackedAliveAt750ms[i + 1];
      trackedAliveAt1s[i] = trackedAliveAt1s[i + 1];
      trackedAliveAt1500ms[i] = trackedAliveAt1500ms[i + 1];
      trackedAliveAt2s[i] = trackedAliveAt2s[i + 1];
      trackedAliveAt3s[i] = trackedAliveAt3s[i + 1];
      trackedSampleMsAt100ms[i] = trackedSampleMsAt100ms[i + 1];
      trackedSampleMsAt250ms[i] = trackedSampleMsAt250ms[i + 1];
      trackedSampleMsAt500ms[i] = trackedSampleMsAt500ms[i + 1];
      trackedSampleMsAt750ms[i] = trackedSampleMsAt750ms[i + 1];
      trackedSampleMsAt1s[i] = trackedSampleMsAt1s[i + 1];
      trackedSampleMsAt1500ms[i] = trackedSampleMsAt1500ms[i + 1];
      trackedSampleMsAt2s[i] = trackedSampleMsAt2s[i + 1];
      trackedSampleMsAt3s[i] = trackedSampleMsAt3s[i + 1];
      trackedTicksAt100ms[i] = trackedTicksAt100ms[i + 1];
      trackedTicksAt250ms[i] = trackedTicksAt250ms[i + 1];
      trackedTicksAt500ms[i] = trackedTicksAt500ms[i + 1];
      trackedTicksAt750ms[i] = trackedTicksAt750ms[i + 1];
      trackedTicksAt1s[i] = trackedTicksAt1s[i + 1];
      trackedTicksAt1500ms[i] = trackedTicksAt1500ms[i + 1];
      trackedTicksAt2s[i] = trackedTicksAt2s[i + 1];
      trackedTicksAt3s[i] = trackedTicksAt3s[i + 1];
      trackedTimeToFirstProfitMs[i] = trackedTimeToFirstProfitMs[i + 1];
      trackedTimeToMfe10Ms[i] = trackedTimeToMfe10Ms[i + 1];
      trackedTimeToMfe20Ms[i] = trackedTimeToMfe20Ms[i + 1];
      trackedTimeToMfe40Ms[i] = trackedTimeToMfe40Ms[i + 1];
      trackedTimeToSpeedMs[i] = trackedTimeToSpeedMs[i + 1];
      trackedFirstProfitSeen[i] = trackedFirstProfitSeen[i + 1];
      trackedPeakAfterFirstProfit[i] = trackedPeakAfterFirstProfit[i + 1];
      trackedMaxPullbackAfterFirstProfit[i] = trackedMaxPullbackAfterFirstProfit[i + 1];
      trackedV461LowDetectSpread[i] = trackedV461LowDetectSpread[i + 1];
      trackedV461LowDetectOrderflowState[i] = trackedV461LowDetectOrderflowState[i + 1];
      trackedV461LowDetectPressureState[i] = trackedV461LowDetectPressureState[i + 1];
      trackedV461OppAtLowMfe[i] = trackedV461OppAtLowMfe[i + 1];
      trackedV461OppAtLowMae[i] = trackedV461OppAtLowMae[i + 1];
      trackedV461OppAtLowWouldSpeed[i] = trackedV461OppAtLowWouldSpeed[i + 1];
      trackedV461OppAtLowWouldHardLose[i] = trackedV461OppAtLowWouldHardLose[i + 1];
      trackedPreEntryHighShadowScores[i] = trackedPreEntryHighShadowScores[i + 1];
      trackedPreEntryHighShadowBuckets[i] = trackedPreEntryHighShadowBuckets[i + 1];
      trackedPreEntryHighWouldAllows[i] = trackedPreEntryHighWouldAllows[i + 1];
      trackedPreEntryHighWouldBlocks[i] = trackedPreEntryHighWouldBlocks[i + 1];
      trackedPreEntryHighSignals[i] = trackedPreEntryHighSignals[i + 1];
      trackedV471TickPath[i] = trackedV471TickPath[i + 1];
      trackedV471PreEntryTapeHealth[i] = trackedV471PreEntryTapeHealth[i + 1];
      trackedV471PreEntryVelocityDecay[i] = trackedV471PreEntryVelocityDecay[i + 1];
      trackedV471PreSpeedSignalAgeMs[i] = trackedV471PreSpeedSignalAgeMs[i + 1];
      trackedV48Mode2Signal[i] = trackedV48Mode2Signal[i + 1];
      trackedV48Mode2BlockReason[i] = trackedV48Mode2BlockReason[i + 1];
      trackedV48Mode2OppFlags[i] = trackedV48Mode2OppFlags[i + 1];
      trackedV48Mode2Velocity1s[i] = trackedV48Mode2Velocity1s[i + 1];
      trackedV48Mode2WeightFactor[i] = trackedV48Mode2WeightFactor[i + 1];
      trackedUrgentCloseStartMs[i] = trackedUrgentCloseStartMs[i + 1];
      trackedFOLMPreHardWarningMasks[i] = trackedFOLMPreHardWarningMasks[i + 1];
      trackedRetestPreFailWarningMasks[i] = trackedRetestPreFailWarningMasks[i + 1];
      trackedRetestFailStartMs[i] = trackedRetestFailStartMs[i + 1];
      trackedRetestFailStartFavs[i] = trackedRetestFailStartFavs[i + 1];
      trackedRetestCollapseStartMs[i] = trackedRetestCollapseStartMs[i + 1];
      trackedRetestCollapseTicks[i] = trackedRetestCollapseTicks[i + 1];
      trackedLastFavs[i] = trackedLastFavs[i + 1];
      trackedLastFavMs[i] = trackedLastFavMs[i + 1];
      trackedLabels[i] = trackedLabels[i + 1];
      trackedSpeedExitPendings[i] = trackedSpeedExitPendings[i + 1];
      trackedSpeedExitLastTryMs[i] = trackedSpeedExitLastTryMs[i + 1];
      trackedSpeedExitRetryCounts[i] = trackedSpeedExitRetryCounts[i + 1];
      trackedSpeedExitLimitLogged[i] = trackedSpeedExitLimitLogged[i + 1];
      trackedSpeedExitUnsafeLogged[i] = trackedSpeedExitUnsafeLogged[i + 1];
      trackedHardFloorUrgentClose[i] = trackedHardFloorUrgentClose[i + 1];
      trackedHardFloorLastLogMs[i] = trackedHardFloorLastLogMs[i + 1];
      trackedHardFloorAttempts[i] = trackedHardFloorAttempts[i + 1];
      trackedRetestCollapseUrgentClose[i] = trackedRetestCollapseUrgentClose[i + 1];
      trackedRetestCollapseLastLogMs[i] = trackedRetestCollapseLastLogMs[i + 1];
      trackedRetestCollapseAttempts[i] = trackedRetestCollapseAttempts[i + 1];
      trackedPreSpeedDefenseUrgentClose[i] = trackedPreSpeedDefenseUrgentClose[i + 1];
      trackedPreSpeedDefenseLastLogMs[i] = trackedPreSpeedDefenseLastLogMs[i + 1];
      trackedPreSpeedDefenseAttempts[i] = trackedPreSpeedDefenseAttempts[i + 1];
      trackedRetestPauseLastLogMs[i] = trackedRetestPauseLastLogMs[i + 1];
   }

   ArrayResize(trackedTickets, n - 1);
   ArrayResize(trackedEntryMs, n - 1);
   ArrayResize(trackedEntries, n - 1);
   ArrayResize(trackedSides, n - 1);
   ArrayResize(trackedMfes, n - 1);
   ArrayResize(trackedMaes, n - 1);
   ArrayResize(trackedHit21s, n - 1);
   ArrayResize(trackedHit37s, n - 1);
   ArrayResize(trackedRetestHelds, n - 1);
   ArrayResize(trackedRetestFaileds, n - 1);
   ArrayResize(trackedFirst10sMfes, n - 1);
   ArrayResize(trackedTickCounts, n - 1);
   ArrayResize(trackedMaxSingleTickAdversePts, n - 1);
   ArrayResize(trackedLastTickDeltaPts, n - 1);
   ArrayResize(trackedEntryTickJumpWithTrades, n - 1);
   ArrayResize(trackedEntryTickJumpAgainstTrades, n - 1);
   ArrayResize(trackedFirst500msMaxAdverseJumpPts, n - 1);
   ArrayResize(trackedFirst1sMaxAdverseJumpPts, n - 1);
   ArrayResize(trackedFirst2sMaxAdverseJumpPts, n - 1);
   ArrayResize(trackedFirst250msMaxAdverseJumpPts, n - 1);
   ArrayResize(trackedFirst750msMaxAdverseJumpPts, n - 1);
   ArrayResize(trackedV44First1sShadowFired, n - 1);
   ArrayResize(trackedV44First1sShadowMs, n - 1);
   ArrayResize(trackedV44First1sShadowFav, n - 1);
   ArrayResize(trackedV44First2sShadowFired, n - 1);
   ArrayResize(trackedV44First2sShadowMs, n - 1);
   ArrayResize(trackedV44First2sShadowFav, n - 1);
   ArrayResize(trackedV451LowJFirst1sFired, n - 1);
   ArrayResize(trackedV451LowJFirst1sMs, n - 1);
   ArrayResize(trackedV451LowJFirst1sFav, n - 1);
   ArrayResize(trackedV451LowJFirst2sFired, n - 1);
   ArrayResize(trackedV451LowJFirst2sMs, n - 1);
   ArrayResize(trackedV451LowJFirst2sFav, n - 1);
   ArrayResize(trackedV451FlowOppSourceTiming, n - 1);
   ArrayResize(trackedV451FlowOppSourceMs, n - 1);
   ArrayResize(trackedV451FlowOppSourceFav, n - 1);
   ArrayResize(trackedV46LowDeadShadowFired, n - 1);
   ArrayResize(trackedV46LowDeadShadowMs, n - 1);
   ArrayResize(trackedV46LowDeadShadowFav, n - 1);
   ArrayResize(trackedV46LowDeadShadowMfe, n - 1);
   ArrayResize(trackedV46LowDeadShadowMaxFav1To3, n - 1);
   ArrayResize(trackedV46LowDeadShadowReason, n - 1);
   ArrayResize(trackedPreWarn15JumpAgainstTrades, n - 1);
   ArrayResize(trackedPreWarn18JumpAgainstTrades, n - 1);
   ArrayResize(trackedPreWarn21JumpAgainstTrades, n - 1);
   ArrayResize(trackedPreWarn24JumpAgainstTrades, n - 1);
   ArrayResize(trackedLastQuoteGapMs, n - 1);
   ArrayResize(trackedLastTelemetryTickMs, n - 1);
   ArrayResize(trackedFOLMWarn15Ms, n - 1);
   ArrayResize(trackedFOLMWarn18Ms, n - 1);
   ArrayResize(trackedFOLMWarn21Ms, n - 1);
   ArrayResize(trackedFOLMWarn24Ms, n - 1);
   ArrayResize(trackedFOLMWarn24Ticks, n - 1);
   ArrayResize(trackedFavAt250ms, n - 1);
   ArrayResize(trackedFavAt500ms, n - 1);
   ArrayResize(trackedFavAt1s, n - 1);
   ArrayResize(trackedFavAt2s, n - 1);
   ArrayResize(trackedFavAt3s, n - 1);
   ArrayResize(trackedFavAt100ms, n - 1);
   ArrayResize(trackedFavAt750ms, n - 1);
   ArrayResize(trackedFavAt1500ms, n - 1);
   ArrayResize(trackedAliveAt100ms, n - 1);
   ArrayResize(trackedAliveAt250ms, n - 1);
   ArrayResize(trackedAliveAt500ms, n - 1);
   ArrayResize(trackedAliveAt750ms, n - 1);
   ArrayResize(trackedAliveAt1s, n - 1);
   ArrayResize(trackedAliveAt1500ms, n - 1);
   ArrayResize(trackedAliveAt2s, n - 1);
   ArrayResize(trackedAliveAt3s, n - 1);
   ArrayResize(trackedSampleMsAt100ms, n - 1);
   ArrayResize(trackedSampleMsAt250ms, n - 1);
   ArrayResize(trackedSampleMsAt500ms, n - 1);
   ArrayResize(trackedSampleMsAt750ms, n - 1);
   ArrayResize(trackedSampleMsAt1s, n - 1);
   ArrayResize(trackedSampleMsAt1500ms, n - 1);
   ArrayResize(trackedSampleMsAt2s, n - 1);
   ArrayResize(trackedSampleMsAt3s, n - 1);
   ArrayResize(trackedTicksAt100ms, n - 1);
   ArrayResize(trackedTicksAt250ms, n - 1);
   ArrayResize(trackedTicksAt500ms, n - 1);
   ArrayResize(trackedTicksAt750ms, n - 1);
   ArrayResize(trackedTicksAt1s, n - 1);
   ArrayResize(trackedTicksAt1500ms, n - 1);
   ArrayResize(trackedTicksAt2s, n - 1);
   ArrayResize(trackedTicksAt3s, n - 1);
   ArrayResize(trackedTimeToFirstProfitMs, n - 1);
   ArrayResize(trackedTimeToMfe10Ms, n - 1);
   ArrayResize(trackedTimeToMfe20Ms, n - 1);
   ArrayResize(trackedTimeToMfe40Ms, n - 1);
   ArrayResize(trackedTimeToSpeedMs, n - 1);
   ArrayResize(trackedFirstProfitSeen, n - 1);
   ArrayResize(trackedPeakAfterFirstProfit, n - 1);
   ArrayResize(trackedMaxPullbackAfterFirstProfit, n - 1);
   ArrayResize(trackedV461LowDetectSpread, n - 1);
   ArrayResize(trackedV461LowDetectOrderflowState, n - 1);
   ArrayResize(trackedV461LowDetectPressureState, n - 1);
   ArrayResize(trackedV461OppAtLowMfe, n - 1);
   ArrayResize(trackedV461OppAtLowMae, n - 1);
   ArrayResize(trackedV461OppAtLowWouldSpeed, n - 1);
   ArrayResize(trackedV461OppAtLowWouldHardLose, n - 1);
   ArrayResize(trackedPreEntryHighShadowScores, n - 1);
   ArrayResize(trackedPreEntryHighShadowBuckets, n - 1);
   ArrayResize(trackedPreEntryHighWouldAllows, n - 1);
   ArrayResize(trackedPreEntryHighWouldBlocks, n - 1);
   ArrayResize(trackedPreEntryHighSignals, n - 1);
   ArrayResize(trackedV471TickPath, n - 1);
   ArrayResize(trackedV471PreEntryTapeHealth, n - 1);
   ArrayResize(trackedV471PreEntryVelocityDecay, n - 1);
   ArrayResize(trackedV471PreSpeedSignalAgeMs, n - 1);
   ArrayResize(trackedV48Mode2Signal, n - 1);
   ArrayResize(trackedV48Mode2BlockReason, n - 1);
   ArrayResize(trackedV48Mode2OppFlags, n - 1);
   ArrayResize(trackedV48Mode2Velocity1s, n - 1);
   ArrayResize(trackedV48Mode2WeightFactor, n - 1);
   ArrayResize(trackedUrgentCloseStartMs, n - 1);
   ArrayResize(trackedFOLMPreHardWarningMasks, n - 1);
   ArrayResize(trackedRetestPreFailWarningMasks, n - 1);
   ArrayResize(trackedRetestFailStartMs, n - 1);
   ArrayResize(trackedRetestFailStartFavs, n - 1);
   ArrayResize(trackedRetestCollapseStartMs, n - 1);
   ArrayResize(trackedRetestCollapseTicks, n - 1);
   ArrayResize(trackedLastFavs, n - 1);
   ArrayResize(trackedLastFavMs, n - 1);
   ArrayResize(trackedLabels, n - 1);
   ArrayResize(trackedSpeedExitPendings, n - 1);
   ArrayResize(trackedSpeedExitLastTryMs, n - 1);
   ArrayResize(trackedSpeedExitRetryCounts, n - 1);
   ArrayResize(trackedSpeedExitLimitLogged, n - 1);
   ArrayResize(trackedSpeedExitUnsafeLogged, n - 1);
   ArrayResize(trackedHardFloorUrgentClose, n - 1);
   ArrayResize(trackedHardFloorLastLogMs, n - 1);
   ArrayResize(trackedHardFloorAttempts, n - 1);
   ArrayResize(trackedRetestCollapseUrgentClose, n - 1);
   ArrayResize(trackedRetestCollapseLastLogMs, n - 1);
   ArrayResize(trackedRetestCollapseAttempts, n - 1);
   ArrayResize(trackedPreSpeedDefenseUrgentClose, n - 1);
   ArrayResize(trackedPreSpeedDefenseLastLogMs, n - 1);
   ArrayResize(trackedPreSpeedDefenseAttempts, n - 1);
   ArrayResize(trackedRetestPauseLastLogMs, n - 1);
}

//+------------------------------------------------------------------+
void TrackerClearAll()
{
   ArrayResize(trackedTickets, 0);
   ArrayResize(closingTickets, 0);
   ArrayResize(closingTicketMs, 0);
   ArrayResize(closingTicketEvents, 0);
   ArrayResize(closeLoggedTickets, 0);
   ArrayResize(closeLoggedTicketMs, 0);
   ArrayResize(closeLoggedTicketEvents, 0);
   ArrayResize(trackedEntryMs, 0);
   ArrayResize(trackedEntries, 0);
   ArrayResize(trackedSides, 0);
   ArrayResize(trackedMfes, 0);
   ArrayResize(trackedMaes, 0);
   ArrayResize(trackedHit21s, 0);
   ArrayResize(trackedHit37s, 0);
   ArrayResize(trackedRetestHelds, 0);
   ArrayResize(trackedRetestFaileds, 0);
   ArrayResize(trackedFirst10sMfes, 0);
   ArrayResize(trackedTickCounts, 0);
   ArrayResize(trackedMaxSingleTickAdversePts, 0);
   ArrayResize(trackedLastTickDeltaPts, 0);
   ArrayResize(trackedEntryTickJumpWithTrades, 0);
   ArrayResize(trackedEntryTickJumpAgainstTrades, 0);
   ArrayResize(trackedFirst500msMaxAdverseJumpPts, 0);
   ArrayResize(trackedFirst1sMaxAdverseJumpPts, 0);
   ArrayResize(trackedFirst2sMaxAdverseJumpPts, 0);
   ArrayResize(trackedFirst250msMaxAdverseJumpPts, 0);
   ArrayResize(trackedFirst750msMaxAdverseJumpPts, 0);
   ArrayResize(trackedV44First1sShadowFired, 0);
   ArrayResize(trackedV44First1sShadowMs, 0);
   ArrayResize(trackedV44First1sShadowFav, 0);
   ArrayResize(trackedV44First2sShadowFired, 0);
   ArrayResize(trackedV44First2sShadowMs, 0);
   ArrayResize(trackedV44First2sShadowFav, 0);
   ArrayResize(trackedV451LowJFirst1sFired, 0);
   ArrayResize(trackedV451LowJFirst1sMs, 0);
   ArrayResize(trackedV451LowJFirst1sFav, 0);
   ArrayResize(trackedV451LowJFirst2sFired, 0);
   ArrayResize(trackedV451LowJFirst2sMs, 0);
   ArrayResize(trackedV451LowJFirst2sFav, 0);
   ArrayResize(trackedV451FlowOppSourceTiming, 0);
   ArrayResize(trackedV451FlowOppSourceMs, 0);
   ArrayResize(trackedV451FlowOppSourceFav, 0);
   ArrayResize(trackedV46LowDeadShadowFired, 0);
   ArrayResize(trackedV46LowDeadShadowMs, 0);
   ArrayResize(trackedV46LowDeadShadowFav, 0);
   ArrayResize(trackedV46LowDeadShadowMfe, 0);
   ArrayResize(trackedV46LowDeadShadowMaxFav1To3, 0);
   ArrayResize(trackedV46LowDeadShadowReason, 0);
   ArrayResize(trackedPreWarn15JumpAgainstTrades, 0);
   ArrayResize(trackedPreWarn18JumpAgainstTrades, 0);
   ArrayResize(trackedPreWarn21JumpAgainstTrades, 0);
   ArrayResize(trackedPreWarn24JumpAgainstTrades, 0);
   ArrayResize(trackedLastQuoteGapMs, 0);
   ArrayResize(trackedLastTelemetryTickMs, 0);
   ArrayResize(trackedFOLMWarn15Ms, 0);
   ArrayResize(trackedFOLMWarn18Ms, 0);
   ArrayResize(trackedFOLMWarn21Ms, 0);
   ArrayResize(trackedFOLMWarn24Ms, 0);
   ArrayResize(trackedFOLMWarn24Ticks, 0);
   ArrayResize(trackedFavAt250ms, 0);
   ArrayResize(trackedFavAt500ms, 0);
   ArrayResize(trackedFavAt1s, 0);
   ArrayResize(trackedFavAt2s, 0);
   ArrayResize(trackedFavAt3s, 0);
   ArrayResize(trackedFavAt100ms, 0);
   ArrayResize(trackedFavAt750ms, 0);
   ArrayResize(trackedFavAt1500ms, 0);
   ArrayResize(trackedAliveAt100ms, 0);
   ArrayResize(trackedAliveAt250ms, 0);
   ArrayResize(trackedAliveAt500ms, 0);
   ArrayResize(trackedAliveAt750ms, 0);
   ArrayResize(trackedAliveAt1s, 0);
   ArrayResize(trackedAliveAt1500ms, 0);
   ArrayResize(trackedAliveAt2s, 0);
   ArrayResize(trackedAliveAt3s, 0);
   ArrayResize(trackedSampleMsAt100ms, 0);
   ArrayResize(trackedSampleMsAt250ms, 0);
   ArrayResize(trackedSampleMsAt500ms, 0);
   ArrayResize(trackedSampleMsAt750ms, 0);
   ArrayResize(trackedSampleMsAt1s, 0);
   ArrayResize(trackedSampleMsAt1500ms, 0);
   ArrayResize(trackedSampleMsAt2s, 0);
   ArrayResize(trackedSampleMsAt3s, 0);
   ArrayResize(trackedTicksAt100ms, 0);
   ArrayResize(trackedTicksAt250ms, 0);
   ArrayResize(trackedTicksAt500ms, 0);
   ArrayResize(trackedTicksAt750ms, 0);
   ArrayResize(trackedTicksAt1s, 0);
   ArrayResize(trackedTicksAt1500ms, 0);
   ArrayResize(trackedTicksAt2s, 0);
   ArrayResize(trackedTicksAt3s, 0);
   ArrayResize(trackedTimeToFirstProfitMs, 0);
   ArrayResize(trackedTimeToMfe10Ms, 0);
   ArrayResize(trackedTimeToMfe20Ms, 0);
   ArrayResize(trackedTimeToMfe40Ms, 0);
   ArrayResize(trackedTimeToSpeedMs, 0);
   ArrayResize(trackedFirstProfitSeen, 0);
   ArrayResize(trackedPeakAfterFirstProfit, 0);
   ArrayResize(trackedMaxPullbackAfterFirstProfit, 0);
   ArrayResize(trackedV461LowDetectSpread, 0);
   ArrayResize(trackedV461LowDetectOrderflowState, 0);
   ArrayResize(trackedV461LowDetectPressureState, 0);
   ArrayResize(trackedV461OppAtLowMfe, 0);
   ArrayResize(trackedV461OppAtLowMae, 0);
   ArrayResize(trackedV461OppAtLowWouldSpeed, 0);
   ArrayResize(trackedV461OppAtLowWouldHardLose, 0);
   ArrayResize(trackedPreEntryHighShadowScores, 0);
   ArrayResize(trackedPreEntryHighShadowBuckets, 0);
   ArrayResize(trackedPreEntryHighWouldAllows, 0);
   ArrayResize(trackedPreEntryHighWouldBlocks, 0);
   ArrayResize(trackedPreEntryHighSignals, 0);
   ArrayResize(trackedV471TickPath, 0);
   ArrayResize(trackedV471PreEntryTapeHealth, 0);
   ArrayResize(trackedV471PreEntryVelocityDecay, 0);
   ArrayResize(trackedV471PreSpeedSignalAgeMs, 0);
   ArrayResize(trackedV48Mode2Signal, 0);
   ArrayResize(trackedV48Mode2BlockReason, 0);
   ArrayResize(trackedV48Mode2OppFlags, 0);
   ArrayResize(trackedV48Mode2Velocity1s, 0);
   ArrayResize(trackedV48Mode2WeightFactor, 0);
   ArrayResize(trackedUrgentCloseStartMs, 0);
   ArrayResize(trackedFOLMPreHardWarningMasks, 0);
   ArrayResize(trackedRetestPreFailWarningMasks, 0);
   ArrayResize(trackedRetestFailStartMs, 0);
   ArrayResize(trackedRetestFailStartFavs, 0);
   ArrayResize(trackedRetestCollapseStartMs, 0);
   ArrayResize(trackedRetestCollapseTicks, 0);
   ArrayResize(trackedLastFavs, 0);
   ArrayResize(trackedLastFavMs, 0);
   ArrayResize(trackedLabels, 0);
   ArrayResize(trackedSpeedExitPendings, 0);
   ArrayResize(trackedSpeedExitLastTryMs, 0);
   ArrayResize(trackedSpeedExitRetryCounts, 0);
   ArrayResize(trackedSpeedExitLimitLogged, 0);
   ArrayResize(trackedSpeedExitUnsafeLogged, 0);
   ArrayResize(trackedHardFloorUrgentClose, 0);
   ArrayResize(trackedHardFloorLastLogMs, 0);
   ArrayResize(trackedHardFloorAttempts, 0);
   ArrayResize(trackedRetestCollapseUrgentClose, 0);
   ArrayResize(trackedRetestCollapseLastLogMs, 0);
   ArrayResize(trackedRetestCollapseAttempts, 0);
   ArrayResize(trackedPreSpeedDefenseUrgentClose, 0);
   ArrayResize(trackedPreSpeedDefenseLastLogMs, 0);
   ArrayResize(trackedPreSpeedDefenseAttempts, 0);
   ArrayResize(trackedRetestPauseLastLogMs, 0);
   ArrayResize(v44GhostTickets, 0);
   ArrayResize(v44GhostStartMs, 0);
   ArrayResize(v44GhostEntries, 0);
   ArrayResize(v44GhostSides, 0);
   ArrayResize(v44GhostActualCloseFavs, 0);
   ArrayResize(v44GhostMfes, 0);
   ArrayResize(v44GhostMaes, 0);
   ArrayResize(v44GhostLabels, 0);
   ArrayResize(v44GhostSourceEvents, 0);
   ArrayResize(pendingRequestTickets, 0);
   ArrayResize(pendingRequestPrices, 0);
   ArrayResize(pendingRequestActions, 0);
   ArrayResize(pendingRequestDecisionMs, 0);
   ArrayResize(pendingRequestAIJourneyContexts, 0);
   ArrayResize(pendingRequestPreEntryHighScores, 0);
   ArrayResize(pendingRequestPreEntryHighBuckets, 0);
   ArrayResize(pendingRequestPreEntryHighAllows, 0);
   ArrayResize(pendingRequestPreEntryHighBlocks, 0);
   ArrayResize(pendingRequestPreEntryHighSignals, 0);
   ArrayResize(pendingRequestV471TapeHealth, 0);
   ArrayResize(pendingRequestV471VelocityDecay, 0);
   ArrayResize(pendingRequestV471PreSpeedSignalAgeMs, 0);
   ArrayResize(pendingRequestV48Mode2Signal, 0);
   ArrayResize(pendingRequestV48Mode2BlockReason, 0);
   ArrayResize(pendingRequestV48Mode2OppFlags, 0);
   ArrayResize(pendingRequestV48Mode2Velocity1s, 0);
   ArrayResize(pendingRequestV48Mode2WeightFactor, 0);
}

//+------------------------------------------------------------------+
void PruneClosingTickets()
{
   PruneCloseLoggedTickets();
   for(int i = ArraySize(closingTickets) - 1; i >= 0; i--)
   {
      ulong ticket = closingTickets[i];
      if(!PositionSelectByTicket(ticket))
      {
         LogInfo("CLOSE_TICKET_RESOLVED", "ticket=" + (string)ticket +
                 " event=" + closingTicketEvents[i] +
                 " age_ms=" + (string)(GetTickMs() - closingTicketMs[i]));
         ClosingTicketRemoveIndex(i);
      }
   }
}

//+------------------------------------------------------------------+
void PruneMissingTrackers()
{
   for(int i = ArraySize(trackedTickets) - 1; i >= 0; i--)
      if(!PositionSelectByTicket(trackedTickets[i]))
      {
         ClearClosingTicket(trackedTickets[i]);
         LogUrgentTrackerGone(i);
         TrackerRemoveIndex(i);
      }
}

//+------------------------------------------------------------------+
void ManagePosition(const MqlTick &t)
{
   if(InpUseContinuationFreeze) CFRBeginManagementPass();
   SRTPrune();
   bool foundAny = false;
   PruneClosingTickets();

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;

      foundAny = true;
      if(IsTicketClosing(ticket))
         continue;

      double entry = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP);
      int side = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1);
      ObserveBurstSettlePosition(ticket, side, t);

      int idx = TrackerIndex(ticket);
      if(idx < 0)
      {
         string labels = PositionGetString(POSITION_COMMENT);
         if(StringLen(labels) <= 0)
            labels = "SPEED_ALERT";
         idx = TrackerAdd(ticket, t.time_msc, entry, side, labels);
         bool trackAlreadyLogged = PositionTrackAlreadyLogged(ticket);
         double requestedEntry = 0.0;
         double preEntryScore = 0.0;
         string preEntryBucket = "";
         string preEntryAllow = "";
         string preEntryBlock = "";
         string preEntrySignals = "";
         string v471TapeHealth = "";
         double v471VelocityDecay = 0.0;
         long v471PreSpeedAgeMs = -1;
         string v48Mode2Signal = "";
         string v48Mode2BlockReason = "";
          int v48Mode2OppFlags = 0;
          double v48Mode2Velocity1s = 0.0;
          double v48Mode2WeightFactor = 1.0;
          TheoryAIPreEntryJourneyContextV1 aiJourneyContext;
          AIPreEntryJourneyResetContext(aiJourneyContext);
          ulong matchedRequestTicket = 0;
          long placementDecisionMs = 0;
         RouterAction trackedAction = ActionFromLabels(labels);
          bool matchedPendingRequest = PendingRequestLookup(ticket, trackedAction, requestedEntry,
                                                            preEntryScore,
                                                            preEntryBucket,
                                                           preEntryAllow,
                                                           preEntryBlock,
                                                           preEntrySignals,
                                                           v471TapeHealth,
                                                           v471VelocityDecay,
                                                           v471PreSpeedAgeMs,
                                                           v48Mode2Signal,
                                                            v48Mode2BlockReason,
                                                            v48Mode2OppFlags,
                                                            v48Mode2Velocity1s,
                                                            v48Mode2WeightFactor,
                                                            aiJourneyContext,
                                                             matchedRequestTicket,
                                                             placementDecisionMs);
          ulong positionIdentifier = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
          long fillEventMs = (long)PositionGetInteger(POSITION_TIME_MSC);
          if(fillEventMs <= 0)
             fillEventMs = t.time_msc;
          AIShadowLogPositionEntry(ticket,
                                   positionIdentifier,
                                   matchedRequestTicket,
                                   trackedAction,
                                   side,
                                   fillEventMs,
                                   placementDecisionMs,
                                   matchedPendingRequest);
           AIPreEntryJourneyLogPositionFill(ticket,
                                            positionIdentifier,
                                           matchedRequestTicket,
                                           trackedAction,
                                           side,
                                           fillEventMs,
                                           placementDecisionMs,
                                           matchedPendingRequest,
                                           aiJourneyContext,
                                           preEntryScore,
                                           preEntryBucket,
                                           preEntrySignals,
                                           v471TapeHealth,
                                           v471VelocityDecay,
                                           v471PreSpeedAgeMs,
                                           v48Mode2Signal,
                                           v48Mode2OppFlags,
                                            v48Mode2Velocity1s,
                                            v48Mode2WeightFactor);
           string t200DecisionIdentity =
              (string)AccountInfoInteger(ACCOUNT_LOGIN) + ":" +
              (string)MagicNumber + ":" + _Symbol + ":" +
              (string)placementDecisionMs + ":" + ActionName(trackedAction);
           if(!matchedPendingRequest || placementDecisionMs <= 0)
              t200DecisionIdentity = "POSITION_IDENTIFIER:" +
                                     (string)positionIdentifier;
           AIT200ShadowStart(ticket,
                             positionIdentifier,
                             placementDecisionMs,
                             fillEventMs,
                             side,
                             entry,
                             sl,
                             ActionName(trackedAction),
                             t200DecisionIdentity);
           if(matchedPendingRequest)
          {
            trackedPreEntryHighShadowScores[idx] = preEntryScore;
            trackedPreEntryHighShadowBuckets[idx] = preEntryBucket;
            trackedPreEntryHighWouldAllows[idx] = preEntryAllow;
            trackedPreEntryHighWouldBlocks[idx] = preEntryBlock;
            trackedPreEntryHighSignals[idx] = preEntrySignals;
            trackedV471PreEntryTapeHealth[idx] = v471TapeHealth;
            trackedV471PreEntryVelocityDecay[idx] = v471VelocityDecay;
            trackedV471PreSpeedSignalAgeMs[idx] = v471PreSpeedAgeMs;
            trackedV48Mode2Signal[idx] = v48Mode2Signal;
            trackedV48Mode2BlockReason[idx] = v48Mode2BlockReason;
            trackedV48Mode2OppFlags[idx] = v48Mode2OppFlags;
            trackedV48Mode2Velocity1s[idx] = v48Mode2Velocity1s;
            trackedV48Mode2WeightFactor[idx] = v48Mode2WeightFactor;
            string v48Mode2Label = V48Mode2LabelText(v48Mode2Signal,
                                                     v48Mode2BlockReason,
                                                     v48Mode2OppFlags,
                                                     v48Mode2Velocity1s,
                                                     v48Mode2WeightFactor);
            if(StringLen(v48Mode2Label) > 0)
               trackedLabels[idx] += ";" + v48Mode2Label;
          }
          else if(!trackAlreadyLogged && UseV471TelemetryRepair)
          {
             LogInfo("POSITION_TRACK_TELEMETRY_MISS",
                     "ticket=" + (string)ticket +
                    " position_identifier=" + (string)positionIdentifier +
                    " action=" + ActionName(trackedAction) +
                    " pending_requests=" + (string)ArraySize(pendingRequestTickets) +
                    " labels=" + labels);
         }
          PositionTrackMarkLogged(ticket);
          if(!trackAlreadyLogged && matchedPendingRequest && requestedEntry > 0.0)
          {
             CaptureTradeMeasurement(requestedEntry, entry, side, false, t, 0);
            SetV45PreEntryHighShadowLog(preEntryScore, preEntryBucket, preEntryAllow, preEntryBlock, preEntrySignals);
            SetV48Mode2ScorecardLog(v48Mode2Signal,
                                     v48Mode2BlockReason,
                                     v48Mode2OppFlags,
                                     v48Mode2Velocity1s,
                                     v48Mode2WeightFactor);
            LogInfo("POSITION_TRACK", "ticket=" + (string)ticket + " side=" + (string)side +
                    " request_ticket=" + (string)matchedRequestTicket +
                    " position_identifier=" + (string)positionIdentifier +
                    " decision_ms=" + (string)placementDecisionMs +
                    " entry=" + DoubleToString(entry, _Digits) +
                    " requested_entry=" + DoubleToString(requestedEntry, _Digits) +
                    " labels=" + trackedLabels[idx]);
         }
      }

      double current = (side > 0 ? t.bid : t.ask);
      double fav = (side > 0 ? (current - entry) : (entry - current)) / _Point;
      if(UseSpeedTrailingExit) SRTObserve(ticket,t);
      trackedMfes[idx] = MathMax(trackedMfes[idx], fav);
      trackedMaes[idx] = MathMin(trackedMaes[idx], fav);
      bool eaExitsReleased = PositionExitProfitReleased(ticket, fav);
      if(InpUseContinuationFreeze)
      {
         CFRProtect(ticket,t);
         if(!CFRProfitMode(ticket,t))
         {
            trackedSpeedExitPendings[idx]=false;
            trackedSpeedExitRetryCounts[idx]=0;
            trackedSpeedExitLimitLogged[idx]=false;
         }
         trackedHardFloorUrgentClose[idx]=false;
         trackedRetestCollapseUrgentClose[idx]=false;
         trackedPreSpeedDefenseUrgentClose[idx]=false;
      }
      int trailLayerIdx = -1;
      if(InpUseTrailLayer || InpUse1000msHold)
      {
         trailLayerIdx = EnsureTrailLayerState(ticket, side, entry, current,
                                               t.time_msc);
         if(side > 0)
            trailLayerStates[trailLayerIdx].peakExecutable =
               MathMax(trailLayerStates[trailLayerIdx].peakExecutable,
                       current);
         else
            trailLayerStates[trailLayerIdx].peakExecutable =
               MathMin(trailLayerStates[trailLayerIdx].peakExecutable,
                       current);
      }
      long heldMsForSnapshot = t.time_msc - trackedEntryMs[idx];
      if(heldMsForSnapshot >= 0 && heldMsForSnapshot <= 10000)
         trackedFirst10sMfes[idx] = MathMax(trackedFirst10sMfes[idx], fav);
      UpdateV41PositionTelemetry(idx, side, fav, t.time_msc);
      AIJourneyShadowMaybeLog(idx,
                              ticket,
                              (ulong)PositionGetInteger(POSITION_IDENTIFIER),
                              side,
                              (long)PositionGetInteger(POSITION_TIME_MSC),
                              t.time_msc);

      if(eaExitsReleased && trackedHardFloorUrgentClose[idx])
      {
         TryHardFloorUrgentRetry(ticket, fav, idx);
         continue;
      }
      if(eaExitsReleased && trackedRetestCollapseUrgentClose[idx])
      {
         TryRetestCollapseUrgentRetry(ticket, fav, idx);
         continue;
      }
      if(eaExitsReleased && trackedPreSpeedDefenseUrgentClose[idx])
      {
         TryPreSpeedDefenseUrgentRetry(ticket, fav, idx);
         continue;
      }

      if(!trackedHit21s[idx] && fav >= MarketFollow21Points)
      {
         trackedHit21s[idx] = true;
         trackedLabels[idx] += ";FOLLOW_21";
         LogInfo("FOLLOW_21", "ticket=" + (string)ticket + " fav=" + DoubleToString(fav, 1) + " labels=" + trackedLabels[idx]);
      }
      if(!trackedHit37s[idx] && fav >= MarketFollow37Points)
      {
         trackedHit37s[idx] = true;
         trackedLabels[idx] += ";FOLLOW_37";
         LogInfo("FOLLOW_37", "ticket=" + (string)ticket + " fav=" + DoubleToString(fav, 1) + " labels=" + trackedLabels[idx]);
      }

      if((eaExitsReleased || (UseSpeedTrailingExit && UseNegativeSpeedExit)) && TrySpeedProfitExit(ticket, side, fav, idx))
         continue;

      if(eaExitsReleased && UsePostEntryValidation)
      {
         ValidatePosition(ticket, fav, idx);
         if(!PositionSelectByTicket(ticket))
            continue;
      }
      TrackFavSnapshot(ticket, idx, fav, t.time_msc);
      if(eaExitsReleased && trailLayerIdx >= 0 &&
         ProcessPostFillHold(ticket, t, fav,
                             trailLayerStates[trailLayerIdx]))
         continue;
      if(UseTrailing && PositionSelectByTicket(ticket))
         TrailPosition(ticket, side, entry, sl, tp, t);
      if(trailLayerIdx >= 0 && PositionSelectByTicket(ticket))
         ManageTrailLayer(ticket, side, t,
                          trailLayerStates[trailLayerIdx]);
   }

   PruneExitProfitGateStates();
   if(InpWaitForBurstSettle)
      PruneBurstSettleStates();
   PruneTrailLayerStates();
   PruneMissingTrackers();
}

//+------------------------------------------------------------------+
void UpdateV41PositionTelemetry(const int idx, const int side, const double fav, const long nowMs)
{
   if(!UseV41FOLMTickGapTelemetry)
      return;
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return;
   if(nowMs <= 0 || trackedLastTelemetryTickMs[idx] == nowMs)
      return;

   trackedLastTelemetryTickMs[idx] = nowMs;
   trackedTickCounts[idx]++;

   long heldMs = nowMs - trackedEntryMs[idx];
   if(heldMs >= 1000 && trackedFavAt1s[idx] > ROUTER_BIG_VALUE * 0.5)
      trackedFavAt1s[idx] = fav;
   if(heldMs >= 2000 && trackedFavAt2s[idx] > ROUTER_BIG_VALUE * 0.5)
      trackedFavAt2s[idx] = fav;
   if(heldMs >= 3000 && trackedFavAt3s[idx] > ROUTER_BIG_VALUE * 0.5)
      trackedFavAt3s[idx] = fav;
   if(UseV461MicroTelemetry)
   {
      if(heldMs >= 250 && trackedFavAt250ms[idx] > ROUTER_BIG_VALUE * 0.5)
         trackedFavAt250ms[idx] = fav;
      if(heldMs >= 500 && trackedFavAt500ms[idx] > ROUTER_BIG_VALUE * 0.5)
         trackedFavAt500ms[idx] = fav;
      RecordFirstProfitTelemetry(idx, heldMs, fav, false);
      if(trackedTimeToMfe10Ms[idx] <= 0 && fav >= V461Mfe10LevelPoints)
         trackedTimeToMfe10Ms[idx] = (heldMs > 0 ? heldMs : 0);
      if(trackedTimeToMfe20Ms[idx] <= 0 && fav >= V461Mfe20LevelPoints)
         trackedTimeToMfe20Ms[idx] = (heldMs > 0 ? heldMs : 0);
      if(trackedTimeToMfe40Ms[idx] <= 0 && fav >= V461Mfe40LevelPoints)
         trackedTimeToMfe40Ms[idx] = (heldMs > 0 ? heldMs : 0);
      if(trackedTimeToSpeedMs[idx] <= 0 && fav >= SpeedProfitExitPoints)
         trackedTimeToSpeedMs[idx] = (heldMs > 0 ? heldMs : 0);
   }
   V471TrackStageSnapshots(idx, heldMs, fav);
   TrackV451FlowOppSource(idx, heldMs, fav);

   int n = ArraySize(tickMs);
   if(n < 2)
      return;

   long gapMs = tickMs[n - 1] - tickMs[n - 2];
   if(gapMs < 0)
      gapMs = 0;
   trackedLastQuoteGapMs[idx] = gapMs;

   double rawDeltaPts = (tickMid[n - 1] - tickMid[n - 2]) / _Point;
   double favorableDeltaPts = (side > 0 ? rawDeltaPts : -rawDeltaPts);
   double adverseDeltaPts = -favorableDeltaPts;
   trackedLastTickDeltaPts[idx] = adverseDeltaPts;
   if(adverseDeltaPts > trackedMaxSingleTickAdversePts[idx])
      trackedMaxSingleTickAdversePts[idx] = adverseDeltaPts;
   if((UseV43EarlyJumpTelemetry || UseV471TelemetryRepair) && adverseDeltaPts > 0.0)
   {
      if(heldMs <= 250 && adverseDeltaPts > trackedFirst250msMaxAdverseJumpPts[idx])
         trackedFirst250msMaxAdverseJumpPts[idx] = adverseDeltaPts;
      if(heldMs <= 500 && adverseDeltaPts > trackedFirst500msMaxAdverseJumpPts[idx])
         trackedFirst500msMaxAdverseJumpPts[idx] = adverseDeltaPts;
      if(heldMs <= 750 && adverseDeltaPts > trackedFirst750msMaxAdverseJumpPts[idx])
         trackedFirst750msMaxAdverseJumpPts[idx] = adverseDeltaPts;
      if(heldMs <= 1000 && adverseDeltaPts > trackedFirst1sMaxAdverseJumpPts[idx])
         trackedFirst1sMaxAdverseJumpPts[idx] = adverseDeltaPts;
      if(heldMs <= 2000 && adverseDeltaPts > trackedFirst2sMaxAdverseJumpPts[idx])
         trackedFirst2sMaxAdverseJumpPts[idx] = adverseDeltaPts;
   }
   V471AppendTickCapsule(idx, heldMs, fav, adverseDeltaPts, tickSpread[n - 1]);

   if(UseV44ShadowReplayTelemetry)
   {
      if(!trackedV44First1sShadowFired[idx] &&
         V44ShadowFirst1sAdverseJumpPoints > 0.0 &&
         heldMs <= 1000 &&
         trackedFirst1sMaxAdverseJumpPts[idx] >= V44ShadowFirst1sAdverseJumpPoints)
      {
         trackedV44First1sShadowFired[idx] = true;
         trackedV44First1sShadowMs[idx] = heldMs;
         trackedV44First1sShadowFav[idx] = fav;
         if(!TrackedLabelHas(idx, "V44_SHADOW_1S15"))
            trackedLabels[idx] += ";V44_SHADOW_1S15";
      }

      if(!trackedV44First2sShadowFired[idx] &&
         V44ShadowFirst2sAdverseJumpPoints > 0.0 &&
         heldMs <= 2000 &&
         trackedFirst2sMaxAdverseJumpPts[idx] >= V44ShadowFirst2sAdverseJumpPoints)
      {
         trackedV44First2sShadowFired[idx] = true;
         trackedV44First2sShadowMs[idx] = heldMs;
         trackedV44First2sShadowFav[idx] = fav;
         if(!TrackedLabelHas(idx, "V44_SHADOW_2S18"))
            trackedLabels[idx] += ";V44_SHADOW_2S18";
      }
   }

   if(UseV451ProofTelemetry && TrackedLabelHas(idx, "SAR:FOLM"))
   {
      if(!trackedV451LowJFirst1sFired[idx] &&
         V451LOWJFirst1sAdversePoints > 0.0 &&
         heldMs <= 1000 &&
         trackedFirst1sMaxAdverseJumpPts[idx] >= V451LOWJFirst1sAdversePoints)
      {
         trackedV451LowJFirst1sFired[idx] = true;
         trackedV451LowJFirst1sMs[idx] = heldMs;
         trackedV451LowJFirst1sFav[idx] = fav;
         if(!TrackedLabelHas(idx, "V451_LOWJ_1S10_SHADOW"))
            trackedLabels[idx] += ";V451_LOWJ_1S10_SHADOW";
      }

      if(!trackedV451LowJFirst2sFired[idx] &&
         V451LOWJFirst2sAdversePoints > 0.0 &&
         heldMs <= 2000 &&
         trackedFirst2sMaxAdverseJumpPts[idx] >= V451LOWJFirst2sAdversePoints)
      {
         trackedV451LowJFirst2sFired[idx] = true;
         trackedV451LowJFirst2sMs[idx] = heldMs;
         trackedV451LowJFirst2sFav[idx] = fav;
         if(!TrackedLabelHas(idx, "V451_LOWJ_2S12_SHADOW"))
            trackedLabels[idx] += ";V451_LOWJ_2S12_SHADOW";
      }
   }

   if(UseV46LowDeadShadowReplay && TrackedLabelHas(idx, "SAR:FOLM"))
   {
      bool validFav1 = ValidTelemetrySnapshot(trackedFavAt1s[idx]);
      bool validFav2 = ValidTelemetrySnapshot(trackedFavAt2s[idx]);
      bool validFav3 = ValidTelemetrySnapshot(trackedFavAt3s[idx]);
      double maxFav1To3 = V452MaxFav1To3(trackedFavAt1s[idx], trackedFavAt2s[idx], trackedFavAt3s[idx]);
      bool hasMaxFav = (maxFav1To3 > -ROUTER_BIG_VALUE * 0.5);
      bool ageOk = (heldMs >= V46LowDeadShadowMinAgeMs);
      bool maxFavOk = (validFav1 && validFav2 && validFav3 &&
                       hasMaxFav &&
                       maxFav1To3 <= V46LowDeadShadowMaxFav1To3Points);
      bool mfeOk = (trackedFirst10sMfes[idx] <= V46LowDeadShadowMfeCeilingPoints);
      bool currentFavOk = (!V46LowDeadShadowRequireCurrentFavNonPositive || fav <= 0.0);

      if(!trackedV46LowDeadShadowFired[idx] &&
         ageOk &&
         maxFavOk &&
         mfeOk &&
         currentFavOk)
      {
         trackedV46LowDeadShadowFired[idx] = true;
         trackedV46LowDeadShadowMs[idx] = heldMs;
         trackedV46LowDeadShadowFav[idx] = fav;
         trackedV46LowDeadShadowMfe[idx] = trackedFirst10sMfes[idx];
         trackedV46LowDeadShadowMaxFav1To3[idx] = maxFav1To3;
         if(UseV461MicroTelemetry)
         {
            trackedV461LowDetectSpread[idx] = tickSpread[n - 1];
            trackedV461LowDetectOrderflowState[idx] = V461OrderflowStateName(trackedLabels[idx]);
            trackedV461LowDetectPressureState[idx] = V461PressureStateName(trackedLabels[idx]);
            trackedV461OppAtLowMfe[idx] = 0.0;
            trackedV461OppAtLowMae[idx] = 0.0;
            trackedV461OppAtLowWouldSpeed[idx] = false;
            trackedV461OppAtLowWouldHardLose[idx] = false;
         }
         trackedV46LowDeadShadowReason[idx] = "FOLM_MAX_FAV_1TO3_LE_" +
                                              DoubleToString(V46LowDeadShadowMaxFav1To3Points, 1) +
                                              ";MFE_LE_" +
                                              DoubleToString(V46LowDeadShadowMfeCeilingPoints, 1) +
                                              (currentFavOk ? ";CURRENT_FAV_NONPOSITIVE" : "");
         if(!TrackedLabelHas(idx, "V46_LOW_DEAD_SHADOW"))
            trackedLabels[idx] += ";V46_LOW_DEAD_SHADOW";
      }
   }

   if(UseV461MicroTelemetry && trackedV46LowDeadShadowFired[idx])
   {
      double oppositeFavFromLow = trackedV46LowDeadShadowFav[idx] - fav;
      if(oppositeFavFromLow > trackedV461OppAtLowMfe[idx])
         trackedV461OppAtLowMfe[idx] = oppositeFavFromLow;
      if(oppositeFavFromLow < trackedV461OppAtLowMae[idx])
         trackedV461OppAtLowMae[idx] = oppositeFavFromLow;
      if(V461OppositeSpeedPoints > 0.0 && trackedV461OppAtLowMfe[idx] >= V461OppositeSpeedPoints)
         trackedV461OppAtLowWouldSpeed[idx] = true;
      if(V461OppositeHardLossPoints > 0.0 && trackedV461OppAtLowMae[idx] <= -V461OppositeHardLossPoints)
         trackedV461OppAtLowWouldHardLose[idx] = true;
   }
}

//+------------------------------------------------------------------+
void TrackFavSnapshot(const ulong ticket, const int idx, const double fav, const long ms)
{
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return;
   if(trackedTickets[idx] != ticket)
      return;

   trackedLastFavs[idx] = fav;
   trackedLastFavMs[idx] = ms;
}

//+------------------------------------------------------------------+
int V44GhostIndex(const ulong ticket)
{
   for(int i = 0; i < ArraySize(v44GhostTickets); i++)
   {
      if(v44GhostTickets[i] == ticket)
         return i;
   }
   return -1;
}

//+------------------------------------------------------------------+
void RemoveV44GhostIndex(const int idx)
{
   int n = ArraySize(v44GhostTickets);
   if(idx < 0 || idx >= n)
      return;

   for(int i = idx; i < n - 1; i++)
   {
      v44GhostTickets[i] = v44GhostTickets[i + 1];
      v44GhostStartMs[i] = v44GhostStartMs[i + 1];
      v44GhostEntries[i] = v44GhostEntries[i + 1];
      v44GhostSides[i] = v44GhostSides[i + 1];
      v44GhostActualCloseFavs[i] = v44GhostActualCloseFavs[i + 1];
      v44GhostMfes[i] = v44GhostMfes[i + 1];
      v44GhostMaes[i] = v44GhostMaes[i + 1];
      v44GhostLabels[i] = v44GhostLabels[i + 1];
      v44GhostSourceEvents[i] = v44GhostSourceEvents[i + 1];
   }

   ArrayResize(v44GhostTickets, n - 1);
   ArrayResize(v44GhostStartMs, n - 1);
   ArrayResize(v44GhostEntries, n - 1);
   ArrayResize(v44GhostSides, n - 1);
   ArrayResize(v44GhostActualCloseFavs, n - 1);
   ArrayResize(v44GhostMfes, n - 1);
   ArrayResize(v44GhostMaes, n - 1);
   ArrayResize(v44GhostLabels, n - 1);
   ArrayResize(v44GhostSourceEvents, n - 1);
}

//+------------------------------------------------------------------+
void StartV44FOLMSGhost(const ulong ticket, const int idx, const double actualCloseFav, const string sourceEvent)
{
   if(!UseV44ShadowReplayTelemetry || !UseV44FOLMSGhostTracker)
      return;
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return;
   if(!TrackedLabelHas(idx, "SAR:FOLM:SM"))
      return;
   if(V44GhostIndex(ticket) >= 0)
      return;

   int n = ArraySize(v44GhostTickets);
   ArrayResize(v44GhostTickets, n + 1);
   ArrayResize(v44GhostStartMs, n + 1);
   ArrayResize(v44GhostEntries, n + 1);
   ArrayResize(v44GhostSides, n + 1);
   ArrayResize(v44GhostActualCloseFavs, n + 1);
   ArrayResize(v44GhostMfes, n + 1);
   ArrayResize(v44GhostMaes, n + 1);
   ArrayResize(v44GhostLabels, n + 1);
   ArrayResize(v44GhostSourceEvents, n + 1);

   v44GhostTickets[n] = ticket;
   v44GhostStartMs[n] = GetTickMs();
   v44GhostEntries[n] = trackedEntries[idx];
   v44GhostSides[n] = trackedSides[idx];
   v44GhostActualCloseFavs[n] = actualCloseFav;
   v44GhostMfes[n] = actualCloseFav;
   v44GhostMaes[n] = actualCloseFav;
   v44GhostLabels[n] = trackedLabels[idx];
   v44GhostSourceEvents[n] = sourceEvent;

   if(!TrackedLabelHas(idx, "V44_FOLM_SM_GHOST_ARMED"))
      trackedLabels[idx] += ";V44_FOLM_SM_GHOST_ARMED";
   logV44FOLMSGhostStarted = "true";
}

//+------------------------------------------------------------------+
void LogV44FOLMSGhostOutcome(const int idx, const string outcome, const double fav, const long heldMs)
{
   if(idx < 0 || idx >= ArraySize(v44GhostTickets))
      return;

   string eventName = "V44_FOLM_SM_GHOST_" + outcome;
   LogInfo(eventName,
           "ticket=" + (string)v44GhostTickets[idx] +
           " ghost_fav=" + DoubleToString(fav, 1) +
           " ghost_mfe=" + DoubleToString(v44GhostMfes[idx], 1) +
           " ghost_mae=" + DoubleToString(v44GhostMaes[idx], 1) +
           " ghost_held_ms=" + (string)heldMs +
           " actual_close_fav=" + DoubleToString(v44GhostActualCloseFavs[idx], 1) +
           " source_event=" + v44GhostSourceEvents[idx] +
           " win_level=" + DoubleToString(V44FOLMSGhostWinPoints, 1) +
           " loss_level=" + DoubleToString(V44FOLMSGhostLossPoints, 1) +
           " labels=" + v44GhostLabels[idx]);
}

//+------------------------------------------------------------------+
void UpdateV44FOLMSGhosts(const MqlTick &t)
{
   if(!UseV44ShadowReplayTelemetry || !UseV44FOLMSGhostTracker)
      return;

   long nowMs = t.time_msc;
   if(nowMs <= 0)
      nowMs = GetTickMs();

   for(int i = ArraySize(v44GhostTickets) - 1; i >= 0; i--)
   {
      double current = (v44GhostSides[i] > 0 ? t.bid : t.ask);
      double fav = (v44GhostSides[i] > 0
                    ? (current - v44GhostEntries[i])
                    : (v44GhostEntries[i] - current)) / _Point;
      if(fav > v44GhostMfes[i])
         v44GhostMfes[i] = fav;
      if(fav < v44GhostMaes[i])
         v44GhostMaes[i] = fav;

      long heldMs = nowMs - v44GhostStartMs[i];
      if(heldMs < 0)
         heldMs = 0;

      if(V44FOLMSGhostWinPoints > 0.0 && fav >= V44FOLMSGhostWinPoints)
      {
         LogV44FOLMSGhostOutcome(i, "SPEED_WIN", fav, heldMs);
         RemoveV44GhostIndex(i);
         continue;
      }

      if(V44FOLMSGhostLossPoints > 0.0 && fav <= -V44FOLMSGhostLossPoints)
      {
         LogV44FOLMSGhostOutcome(i, "WARN24_LOSS", fav, heldMs);
         RemoveV44GhostIndex(i);
         continue;
      }

      if(V44FOLMSGhostMaxSeconds > 0 && heldMs >= (long)V44FOLMSGhostMaxSeconds * 1000)
      {
         LogV44FOLMSGhostOutcome(i, "EXPIRED", fav, heldMs);
         RemoveV44GhostIndex(i);
      }
   }
}

//+------------------------------------------------------------------+
bool TrySpeedProfitExit(const ulong ticket, const int side, const double fav, const int idx)
{
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return false;
   if(UseSpeedTrailingExit) return SRTTryExit(ticket,idx);
   if(!UseSpeedProfitExit)
      return false;
   if(InpUseContinuationFreeze)
   {
      MqlTick current;
      if(!SymbolInfoTick(_Symbol,current) || !CFRProfitMode(ticket,current))
      {
         trackedSpeedExitPendings[idx]=false;
         trackedSpeedExitRetryCounts[idx]=0;
         trackedSpeedExitLimitLogged[idx]=false;
         return false;
      }
   }

   double predictiveRisk = 0.0;
   double predictiveVelocity = 0.0;
   double predictiveAdverse = 0.0;
   double predictiveSpread = 0.0;
   double projectedNet = fav;
   bool targetReady = (fav >= SpeedProfitExitPoints);
   bool predictiveReady = false;

   if(UsePredictiveSpeedProfitExit)
   {
      predictiveRisk = PredictiveSpeedExitRiskPoints(side, predictiveVelocity, predictiveAdverse, predictiveSpread);
      projectedNet = fav - predictiveRisk;
      bool profitSideSpeed = (speedActive && (!RequireProfitSideSpeed || speedDir == side));
      predictiveReady = (profitSideSpeed &&
                         fav >= PredictiveExitMinProfitPoints &&
                         projectedNet >= PredictiveExitMinProjectedNetPoints);
   }

   bool pendingExit = (idx >= 0 && idx < ArraySize(trackedSpeedExitPendings) && trackedSpeedExitPendings[idx]);
   if((!pendingExit || InpUseContinuationFreeze) && !targetReady && !predictiveReady)
      return false;

   if(!pendingExit || InpUseContinuationFreeze)
   {
      if(!speedActive)
         return false;
      if(RequireProfitSideSpeed && speedDir != side)
         return false;
   }

   if(UsePredictiveSpeedProfitExit && trackedSpeedExitUnsafeLogged[idx] &&
      projectedNet >= PredictiveExitMinProjectedNetPoints)
   {
      trackedSpeedExitUnsafeLogged[idx] = false;
      LogInfo("SPEED_PROFIT_EXIT_SAFE_AGAIN", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " projected_net=" + DoubleToString(projectedNet, 1) +
              " risk=" + DoubleToString(predictiveRisk, 1));
   }

   if(UsePredictiveSpeedProfitExit && BlockSpeedExitIfProjectedNegative && projectedNet < 0.0)
   {
      trackedSpeedExitPendings[idx] = false;
      if(!trackedSpeedExitUnsafeLogged[idx])
      {
         trackedSpeedExitUnsafeLogged[idx] = true;
         LogInfo("SPEED_PROFIT_EXIT_PROJECTED_NEGATIVE", "ticket=" + (string)ticket +
                 " fav=" + DoubleToString(fav, 1) +
                 " projected_net=" + DoubleToString(projectedNet, 1) +
                 " risk=" + DoubleToString(predictiveRisk, 1) +
                 " velocity_pts_sec=" + DoubleToString(predictiveVelocity, 1) +
                 " adverse_pts=" + DoubleToString(predictiveAdverse, 1) +
                 " spread=" + DoubleToString(predictiveSpread, 1));
      }
      return false;
   }

   long nowMs = GetTickMs();
   if(pendingExit && SpeedProfitExitRetrySeconds > 0 &&
      nowMs - trackedSpeedExitLastTryMs[idx] < SpeedProfitExitRetrySeconds * 1000)
      return false;

   if(SpeedProfitExitMaxRetries > 0 && trackedSpeedExitRetryCounts[idx] >= SpeedProfitExitMaxRetries)
   {
      if(!trackedSpeedExitLimitLogged[idx])
      {
         trackedSpeedExitLimitLogged[idx] = true;
         LogInfo("SPEED_PROFIT_EXIT_RETRY_LIMIT", "ticket=" + (string)ticket +
                 " attempts=" + (string)trackedSpeedExitRetryCounts[idx] +
                 " fav=" + DoubleToString(fav, 1) +
                 " labels=" + trackedLabels[idx]);
      }
      return false;
   }

   trackedSpeedExitPendings[idx] = true;
   trackedSpeedExitLastTryMs[idx] = nowMs;
   trackedSpeedExitRetryCounts[idx]++;

   string exitMode = (predictiveReady && !targetReady ? "PREDICTIVE_EXIT" : "TARGET_EXIT");
   string labels = trackedLabels[idx] + ";" + exitMode + ";SPEED_PROFIT_EXIT";
   bool closed = ClosePositionWithComment(ticket, SpeedProfitExitComment, CONT_EXIT_PROFIT, 0.0);
   if(closed)
   {
      LogInfo("SPEED_PROFIT_EXIT", "ticket=" + (string)ticket +
              " mode=" + exitMode +
              " fav=" + DoubleToString(fav, 1) +
              " projected_net=" + DoubleToString(projectedNet, 1) +
              " risk=" + DoubleToString(predictiveRisk, 1) +
              " velocity_pts_sec=" + DoubleToString(predictiveVelocity, 1) +
              " adverse_pts=" + DoubleToString(predictiveAdverse, 1) +
              " spread=" + DoubleToString(predictiveSpread, 1) +
              " speed_dir=" + (string)speedDir +
              " speed_pts=" + DoubleToString(speedPoints, 1) +
              " labels=" + labels);
      TrackerRemoveIndex(idx);
      speedActive = false;
      return true;
   }

   if(lastCloseRetcode == SAR_RETCODE_CLOSE_ORDER_EXISTS)
   {
      if(trackedSpeedExitRetryCounts[idx] > 0)
         trackedSpeedExitRetryCounts[idx]--;
      LogInfo("SPEED_PROFIT_CLOSE_PENDING", "ticket=" + (string)ticket +
              " retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " projected_net=" + DoubleToString(projectedNet, 1) +
              " risk=" + DoubleToString(predictiveRisk, 1) +
              " next_check_sec=" + (string)SpeedProfitExitRetrySeconds);
      return false;
   }

   if(lastCloseRetcode == SAR_RETCODE_POSITION_CLOSED && !PositionSelectByTicket(ticket))
   {
      LogInfo("SPEED_PROFIT_POSITION_GONE", "ticket=" + (string)ticket +
              " retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription);
      TrackerRemoveIndex(idx);
      return true;
   }

   LogInfo("SPEED_PROFIT_EXIT_FAILED", "ticket=" + (string)ticket +
           " attempt=" + (string)trackedSpeedExitRetryCounts[idx] +
           " retcode=" + (string)lastCloseRetcode +
           " " + lastCloseRetcodeDescription +
           " projected_net=" + DoubleToString(projectedNet, 1) +
           " risk=" + DoubleToString(predictiveRisk, 1) +
           " next_retry_sec=" + (string)SpeedProfitExitRetrySeconds);
   return false;
}

//+------------------------------------------------------------------+
double PredictiveSpeedExitRiskPoints(const int side,
                                     double &velocityPtsSec,
                                     double &adversePts,
                                     double &spreadPts)
{
   velocityPtsSec = 0.0;
   adversePts = 0.0;
   spreadPts = 0.0;

   int n = ArraySize(tickMs);
   if(n <= 1)
      return PredictiveExitMinRiskBufferPoints + PredictiveExitExtraBufferPoints;

   int lookbackMs = MathMax(1, PredictiveExitVelocityLookbackMs);
   long nowMs = tickMs[n - 1];
   int idx = FirstTickAtOrAfter(nowMs - lookbackMs);
   if(idx < 0)
      idx = 0;
   if(idx >= n - 1)
      idx = MathMax(0, n - 2);

   double currentMid = tickMid[n - 1];
   double oldestMid = tickMid[idx];
   double dtSec = MathMax(0.001, (double)(nowMs - tickMs[idx]) / 1000.0);
   double absoluteVelocity = MathAbs((currentMid - oldestMid) / _Point) / dtSec;

   double peak = currentMid;
   double trough = currentMid;
   long peakMs = nowMs;
   long troughMs = nowMs;
   for(int i = idx; i < n; i++)
   {
      if(tickMid[i] > peak)
      {
         peak = tickMid[i];
         peakMs = tickMs[i];
      }
      if(tickMid[i] < trough)
      {
         trough = tickMid[i];
         troughMs = tickMs[i];
      }
   }

   double adverseVelocity = 0.0;
   if(side > 0)
   {
      adversePts = MathMax(0.0, (peak - currentMid) / _Point);
      if(adversePts > 0.0)
         adverseVelocity = adversePts / MathMax(0.001, (double)(nowMs - peakMs) / 1000.0);
   }
   else
   {
      adversePts = MathMax(0.0, (currentMid - trough) / _Point);
      if(adversePts > 0.0)
         adverseVelocity = adversePts / MathMax(0.001, (double)(nowMs - troughMs) / 1000.0);
   }

   velocityPtsSec = MathMax(absoluteVelocity, adverseVelocity);
   spreadPts = MathMax(0.0, tickSpread[n - 1]);

   double latencySec = MathMax(0.0, (double)PredictiveExitLatencyMs / 1000.0);
   double velocityRisk = velocityPtsSec * latencySec * MathMax(0.0, PredictiveExitVelocityMultiplier);
   double risk = spreadPts + PredictiveExitExtraBufferPoints +
                 MathMax(PredictiveExitMinRiskBufferPoints, velocityRisk);

   if(PredictiveExitMaxRiskBufferPoints > 0.0)
      risk = MathMin(risk, PredictiveExitMaxRiskBufferPoints);

   return MathMax(0.0, risk);
}

//+------------------------------------------------------------------+
// EA market-close rules resume once this position first exceeds +6.8 pips.
// Keep this latch separate from trackers, which may be removed on partial fills.
string ExitProfitGateKey(const long positionId)
{
   uint serverHash = 2166136261;
   string server = AccountInfoString(ACCOUNT_SERVER);
   for(int i = 0; i < StringLen(server); i++)
      serverHash = (serverHash ^ (uint)StringGetCharacter(server, i)) * 16777619;
   // Maximum 59 characters for positive signed-64-bit account/position IDs.
   return "SAR_E68_" + (string)AccountInfoInteger(ACCOUNT_LOGIN) + "_" +
          (string)serverHash + "_" + (string)positionId;
}

//+------------------------------------------------------------------+
bool PositionExitProfitReleased(const ulong ticket, const double favourablePoints)
{
   if(!PositionSelectByTicket(ticket))
      return false;
   long positionId = PositionGetInteger(POSITION_IDENTIFIER);
   if(positionId <= 0)
      return false;
   int side = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1);
   bool tester = (bool)MQLInfoInteger(MQL_TESTER);
   string key = (tester ? "" : ExitProfitGateKey(positionId));
   int idx = -1;
   for(int i = 0; i < ArraySize(exitProfitGateStates); i++)
      if(exitProfitGateStates[i].positionId == positionId)
      {
         idx = i;
         break;
      }
   if(idx < 0)
   {
      idx = ArraySize(exitProfitGateStates);
      ArrayResize(exitProfitGateStates, idx + 1);
      exitProfitGateStates[idx].positionId = positionId;
      exitProfitGateStates[idx].side = side;
      exitProfitGateStates[idx].released = false;
   }
   if(exitProfitGateStates[idx].side != side)
   {
      // Netting can reverse direction without changing POSITION_IDENTIFIER.
      exitProfitGateStates[idx].side = side;
      exitProfitGateStates[idx].released = false;
      if(!tester)
         GlobalVariableDel(key);
   }
   if(!tester && GlobalVariableCheck(key))
   {
      double savedSide = GlobalVariableGet(key);
      if(savedSide == (double)side)
         exitProfitGateStates[idx].released = true;
      else
         GlobalVariableDel(key);
   }
   if(exitProfitGateStates[idx].released)
      return true;
   if(!TrailingActivationProfitReached(favourablePoints))
      return false;

   exitProfitGateStates[idx].released = true;
   if(!tester)
   {
      if(GlobalVariableSet(key, (double)side) > 0)
         GlobalVariablesFlush();
      else
         Print("EXIT_GATE_PERSIST_FAILED position_id=", positionId,
               " error=", GetLastError());
   }
   LogInfo("EXIT_GATE_RELEASED",
           "ticket=" + (string)ticket + " position_id=" + (string)positionId +
           " fav_points=" + DoubleToString(favourablePoints, 3) +
           " threshold_pips=6.8 mode=FIRST_CROSSING");
   return true;
}

//+------------------------------------------------------------------+
void PruneExitProfitGateStates()
{
   for(int i = ArraySize(exitProfitGateStates) - 1; i >= 0; i--)
   {
      bool alive = false;
      for(int j = PositionsTotal() - 1; j >= 0; j--)
         if(PositionGetTicket(j) != 0 &&
            PositionGetInteger(POSITION_IDENTIFIER) == exitProfitGateStates[i].positionId)
         {
            alive = true;
            break;
         }
      if(alive)
         continue;
      if(!MQLInfoInteger(MQL_TESTER))
         GlobalVariableDel(ExitProfitGateKey(exitProfitGateStates[i].positionId));
      int n = ArraySize(exitProfitGateStates);
      for(int j = i; j < n - 1; j++)
         exitProfitGateStates[j] = exitProfitGateStates[j + 1];
      ArrayResize(exitProfitGateStates, n - 1);
   }
}

//+------------------------------------------------------------------+
bool ClosePositionWithComment(const ulong ticket, const string comment,
                              const ContinuationExitReason reason, const double minimumLossPoints)
{
   if(InpUseContinuationFreeze)
      return CFRClosePosition(ticket,comment,reason,minimumLossPoints);
   lastCloseRetcode = 0;
   lastCloseRetcodeDescription = "";

   if(IsTicketClosing(ticket))
   {
      lastCloseRetcode = TRADE_RETCODE_DONE;
      lastCloseRetcodeDescription = "close already started";
      return true;
   }

   if(!PositionSelectByTicket(ticket))
   {
      lastCloseRetcode = SAR_RETCODE_POSITION_CLOSED;
      lastCloseRetcodeDescription = "position closed";
      return false;
   }

   string symbol = PositionGetString(POSITION_SYMBOL);
   double volume = PositionGetDouble(POSITION_VOLUME);
   long type = PositionGetInteger(POSITION_TYPE);
   long positionIdentifier = PositionGetInteger(POSITION_IDENTIFIER);
   int positionSide = (type == POSITION_TYPE_BUY ? 1 : -1);
   if(volume <= 0.0)
      return false;

   MqlTick t;
   if(!SymbolInfoTick(symbol, t))
      return false;

   double exitQuote = (positionSide > 0 ? t.bid : t.ask);
   double entryPrice = PositionGetDouble(POSITION_PRICE_OPEN);
   double favourablePoints = (positionSide > 0 ? exitQuote - entryPrice
                                                : entryPrice - exitQuote) / _Point;
   // Final guard also covers direct calls, urgent retries and the fallback close.
   if(!PositionExitProfitReleased(ticket, favourablePoints))
   {
      lastCloseRetcode = SAR_RETCODE_EXIT_PROFIT_GATE;
      lastCloseRetcodeDescription = "waiting for first profit above 6.8 pips";
      return false;
   }

   MqlTradeRequest request;
   MqlTradeResult result;
   ZeroMemory(request);
   ZeroMemory(result);

   request.action = TRADE_ACTION_DEAL;
   request.symbol = symbol;
   request.magic = MagicNumber;
   request.position = ticket;
   request.volume = volume;
   request.deviation = (ulong)SlippagePoints;
   request.type = (type == POSITION_TYPE_BUY ? ORDER_TYPE_SELL : ORDER_TYPE_BUY);
   request.price = NormalizeDouble((request.type == ORDER_TYPE_BUY ? t.ask : t.bid), _Digits);
   request.type_filling = SymbolFillingMode(symbol);
   request.comment = comment;

   CaptureAutoCloseRuleTelemetry(ticket, positionSide, t, request.price);

   ResetLastError();
   bool orderSent = OrderSend(request, result);
   if(!orderSent && result.retcode == 0)
   {
      result.retcode = (uint)GetLastError();
      result.comment = "OrderSend failed before trade server response";
   }
   if(result.retcode == TRADE_RETCODE_DONE || result.retcode == TRADE_RETCODE_DONE_PARTIAL)
   {
      double fallbackPrice = (request.type == ORDER_TYPE_BUY
                              ? (result.ask > 0.0 ? result.ask : t.ask)
                              : (result.bid > 0.0 ? result.bid : t.bid));
      double executedPrice = DealPriceOrFallback(result.deal, result.price, fallbackPrice);
      CaptureTradeMeasurement(request.price, executedPrice, positionSide, true, t, result.retcode);
      CapturePositionDealLedger(positionIdentifier, !PositionSelectByTicket(ticket));
      CaptureCloseLifecycleFields(ticket, result.deal, executedPrice, logFillMs);
      return true;
   }

   lastCloseRetcode = result.retcode;
   lastCloseRetcodeDescription = result.comment;
   double failedFallbackPrice = (request.type == ORDER_TYPE_BUY
                                 ? (result.ask > 0.0 ? result.ask : t.ask)
                                 : (result.bid > 0.0 ? result.bid : t.bid));
   CaptureTradeMeasurement(request.price, DealPriceOrFallback(result.deal, result.price, failedFallbackPrice), positionSide, true, t, result.retcode);

   if(result.retcode == SAR_RETCODE_CLOSE_ORDER_EXISTS)
      return false;

   MqlTick retryTick = t;
   SymbolInfoTick(symbol, retryTick);
   double retryRequestedPrice = NormalizeDouble((type == POSITION_TYPE_BUY ? retryTick.bid : retryTick.ask), _Digits);
   bool closed = trade.PositionClose(ticket);
   double retryFallbackPrice = (type == POSITION_TYPE_BUY ? retryTick.bid : retryTick.ask);
   ulong retryDealTicket = trade.ResultDeal();
   double retryExecutedPrice = DealPriceOrFallback(retryDealTicket, trade.ResultPrice(), retryFallbackPrice);
   CaptureTradeMeasurement(retryRequestedPrice, retryExecutedPrice, positionSide, true, retryTick, trade.ResultRetcode());
   if(closed || trade.ResultRetcode() == TRADE_RETCODE_DONE || trade.ResultRetcode() == TRADE_RETCODE_DONE_PARTIAL)
   {
      CapturePositionDealLedger(positionIdentifier, !PositionSelectByTicket(ticket));
      CaptureCloseLifecycleFields(ticket, retryDealTicket, retryExecutedPrice, logFillMs);
      return true;
   }

   lastCloseRetcode = trade.ResultRetcode();
   lastCloseRetcodeDescription = trade.ResultRetcodeDescription();
   return false;
}

//+------------------------------------------------------------------+
ENUM_ORDER_TYPE_FILLING SymbolFillingMode(const string symbol)
{
   long filling = SymbolInfoInteger(symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC)
      return ORDER_FILLING_IOC;
   if((filling & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK)
      return ORDER_FILLING_FOK;
   return ORDER_FILLING_RETURN;
}

//+------------------------------------------------------------------+
bool ShouldLogHardFloorRetry(const int idx, const long nowMs)
{
   if(idx < 0 || idx >= ArraySize(trackedHardFloorLastLogMs))
      return false;
   if(RetestHardFloorRetryLogCooldownMs <= 0 ||
      trackedHardFloorLastLogMs[idx] <= 0 ||
      nowMs - trackedHardFloorLastLogMs[idx] >= RetestHardFloorRetryLogCooldownMs)
   {
      trackedHardFloorLastLogMs[idx] = nowMs;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
bool ShouldLogRetestCollapseRetry(const int idx, const long nowMs)
{
   if(idx < 0 || idx >= ArraySize(trackedRetestCollapseLastLogMs))
      return false;
   if(RetestCollapseRetryLogCooldownMs <= 0 ||
      trackedRetestCollapseLastLogMs[idx] <= 0 ||
      nowMs - trackedRetestCollapseLastLogMs[idx] >= RetestCollapseRetryLogCooldownMs)
   {
      trackedRetestCollapseLastLogMs[idx] = nowMs;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
bool ShouldLogPreSpeedDefenseRetry(const int idx, const long nowMs)
{
   if(idx < 0 || idx >= ArraySize(trackedPreSpeedDefenseLastLogMs))
      return false;
   if(PreSpeedAgainstDefenseRetryLogCooldownMs <= 0 ||
      trackedPreSpeedDefenseLastLogMs[idx] <= 0 ||
      nowMs - trackedPreSpeedDefenseLastLogMs[idx] >= PreSpeedAgainstDefenseRetryLogCooldownMs)
   {
      trackedPreSpeedDefenseLastLogMs[idx] = nowMs;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
bool ShouldLogRetestPause(const int idx, const long nowMs)
{
   if(idx < 0 || idx >= ArraySize(trackedRetestPauseLastLogMs))
      return false;
   if(RetestPauseLogCooldownMs <= 0 ||
      trackedRetestPauseLastLogMs[idx] <= 0 ||
      nowMs - trackedRetestPauseLastLogMs[idx] >= RetestPauseLogCooldownMs)
   {
      trackedRetestPauseLastLogMs[idx] = nowMs;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
string FOLMPreHardWarnActiveEventBase()
{
   return "FOLM_PRE_HARD_WARN_" + IntegerToString((int)MathRound(FOLMPreHardWarnActiveClosePoints));
}

//+------------------------------------------------------------------+
void LogUrgentTrackerGone(const int idx)
{
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return;

   ulong ticket = trackedTickets[idx];
   if(trackedRetestCollapseUrgentClose[idx])
   {
      double lastFav = TrackedLastKnownFav(idx);
      string eventBase = RetestUrgentEventBase(idx);
      LogInfo(eventBase + "_RETRY_POSITION_GONE", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(lastFav, 1) +
              " attempts=" + (string)trackedRetestCollapseAttempts[idx] +
              " prune=true labels=" + trackedLabels[idx]);
   }
   if(trackedHardFloorUrgentClose[idx])
   {
      double lastFav = TrackedLastKnownFav(idx);
      LogInfo("RETEST_HARD_FLOOR_RETRY_POSITION_GONE", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(lastFav, 1) +
              " attempts=" + (string)trackedHardFloorAttempts[idx] +
              " prune=true labels=" + trackedLabels[idx]);
   }
   if(trackedPreSpeedDefenseUrgentClose[idx])
   {
      double lastFav = TrackedLastKnownFav(idx);
      bool folmMarketHardUrgent = TrackedLabelHas(idx, "FOLM_MARKET_HARD_URGENT");
      bool folmSellMarketEarlyUrgent = TrackedLabelHas(idx, "FOLM_SM_EARLY_URGENT");
      bool folmPreHardActiveUrgent = TrackedLabelHas(idx, "FOLM_PRE_HARD_ACTIVE_URGENT");
      bool v40PreSpeedShieldUrgent = TrackedLabelHas(idx, "V40_PRE_SPEED_SHIELD_URGENT");
      bool v40FLXQPressureShieldUrgent = TrackedLabelHas(idx, "V40_FLXQ_SS_PRESSURE_SHIELD_URGENT");
      bool flxqSellStopPressureUrgent = TrackedLabelHas(idx, "FLXQ_SS_PRESSURE_URGENT");
      string eventName = "PRE_SPEED_AGAINST_DEFENSE_RETRY_RESOLVED_CLOSE";
      if(folmMarketHardUrgent)
         eventName = "FOLM_MARKET_HARD_CAP_RETRY_RESOLVED_CLOSE";
      else if(folmSellMarketEarlyUrgent)
         eventName = "FOLM_SELL_MARKET_EARLY_DANGER_RETRY_RESOLVED_CLOSE";
      else if(folmPreHardActiveUrgent)
         eventName = FOLMPreHardWarnActiveEventBase() + "_RETRY_RESOLVED_CLOSE";
      else if(v40FLXQPressureShieldUrgent)
         eventName = "V40_FLXQ_SELL_STOP_PRESSURE_SHIELD_RETRY_RESOLVED_CLOSE";
      else if(v40PreSpeedShieldUrgent)
         eventName = "V40_PRE_SPEED_EXECUTION_SHIELD_RETRY_RESOLVED_CLOSE";
      else if(flxqSellStopPressureUrgent)
         eventName = "FLXQ_SELL_STOP_PRESSURE_RETRY_RESOLVED_CLOSE";
      double warningLevel = (folmPreHardActiveUrgent ? FOLMPreHardWarnActiveClosePoints : 0.0);
      long heldMs = GetTickMs() - trackedEntryMs[idx];
      CaptureRuleTelemetry(ticket, idx, lastFav, heldMs, eventName, warningLevel, "URGENT_RESOLVED");
      if(folmSellMarketEarlyUrgent)
         StartV44FOLMSGhost(ticket, idx, lastFav, eventName);
      LogInfo(eventName, "ticket=" + (string)ticket +
              " fav=" + DoubleToString(lastFav, 1) +
              " attempts=" + (string)trackedPreSpeedDefenseAttempts[idx] +
              " resolved=true last_retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " prune=true labels=" + trackedLabels[idx]);
   }
}

//+------------------------------------------------------------------+
void MarkPreSpeedDefenseUrgentClose(const ulong ticket, const double fav, const int idx,
                                    const long heldMs, const bool flowDisagrees,
                                    const bool immediateByFlow, const string preSpeedDetails,
                                    const int waitSeconds, const bool flxqSellStopFastDefense,
                                    const bool stopFlowDanger)
{
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return;

   if(!trackedPreSpeedDefenseUrgentClose[idx])
   {
      trackedPreSpeedDefenseUrgentClose[idx] = true;
      trackedPreSpeedDefenseAttempts[idx] = 0;
      trackedPreSpeedDefenseLastLogMs[idx] = 0;
      trackedUrgentCloseStartMs[idx] = GetTickMs();
      if(StringFind(trackedLabels[idx], "PRE_SPEED_DEFENSE_URGENT") < 0)
         trackedLabels[idx] += ";PRE_SPEED_DEFENSE_URGENT";
      if(stopFlowDanger && StringFind(trackedLabels[idx], "STOP_FLOW_DANGER_URGENT") < 0)
         trackedLabels[idx] += ";STOP_FLOW_DANGER_URGENT";
      string armEvent = (TrackedLabelHas(idx, "V40_FLXQ_SS_PRESSURE_SHIELD_URGENT")
                         ? "V40_FLXQ_SELL_STOP_PRESSURE_SHIELD_RETRY_ARMED"
                         : (TrackedLabelHas(idx, "V40_PRE_SPEED_SHIELD_URGENT")
                            ? "V40_PRE_SPEED_EXECUTION_SHIELD_RETRY_ARMED"
                            : (TrackedLabelHas(idx, "FLXQ_SS_PRESSURE_URGENT")
                         ? "FLXQ_SELL_STOP_PRESSURE_RETRY_ARMED"
                         : (TrackedLabelHas(idx, "FOLM_SM_EARLY_URGENT")
                            ? "FOLM_SELL_MARKET_EARLY_DANGER_RETRY_ARMED"
                            : "PRE_SPEED_AGAINST_DEFENSE_RETRY_ARMED"))));
      LogInfo(armEvent, "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " held_ms=" + (string)heldMs +
              " wait_seconds=" + (string)waitSeconds +
              " flxq_sell_stop_fast=" + (flxqSellStopFastDefense ? "true" : "false") +
              " stop_flow_danger=" + (stopFlowDanger ? "true" : "false") +
              " flow_disagrees=" + (flowDisagrees ? "true" : "false") +
              " immediate_by_flow=" + (immediateByFlow ? "true" : "false") +
              " retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " " + preSpeedDetails +
              " labels=" + trackedLabels[idx]);
   }
}

//+------------------------------------------------------------------+
bool TryPreSpeedDefenseUrgentRetry(const ulong ticket, const double fav, const int idx)
{
   if(InpUseContinuationFreeze) return false;
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return false;
   if(!trackedPreSpeedDefenseUrgentClose[idx])
      return false;

   TrackerSetLastKnownFav(idx, fav);
   trackedPreSpeedDefenseAttempts[idx]++;
   bool stopFlowDangerUrgent = (TrackedLabelHas(idx, "STOP_FLOW_DANGER_URGENT") ||
                                TrackedLabelHas(idx, "SELL_STOP_FLOW_DANGER_URGENT"));
   bool folmMarketHardUrgent = TrackedLabelHas(idx, "FOLM_MARKET_HARD_URGENT");
   bool folmSellMarketEarlyUrgent = TrackedLabelHas(idx, "FOLM_SM_EARLY_URGENT");
   bool folmPreHardActiveUrgent = TrackedLabelHas(idx, "FOLM_PRE_HARD_ACTIVE_URGENT");
   bool v40PreSpeedShieldUrgent = TrackedLabelHas(idx, "V40_PRE_SPEED_SHIELD_URGENT");
   bool v40FLXQPressureShieldUrgent = TrackedLabelHas(idx, "V40_FLXQ_SS_PRESSURE_SHIELD_URGENT");
   bool flxqSellStopPressureUrgent = TrackedLabelHas(idx, "FLXQ_SS_PRESSURE_URGENT");
   string closeComment = PreSpeedAgainstDefenseCloseComment;
   if(v40FLXQPressureShieldUrgent)
      closeComment = V40FLXQSellStopPressureShieldCloseComment;
   else if(v40PreSpeedShieldUrgent)
      closeComment = V40PreSpeedExecutionShieldCloseComment;
   else if(flxqSellStopPressureUrgent)
      closeComment = FLXQSellStopPressureDangerCloseComment;
   else if(stopFlowDangerUrgent)
      closeComment = StopFlowDisagreeDangerCloseComment;
   else if(folmSellMarketEarlyUrgent)
      closeComment = FOLMSellMarketEarlyDangerCloseComment;
   else if(folmPreHardActiveUrgent)
      closeComment = FOLMPreHardWarnActiveCloseComment;
   else if(folmMarketHardUrgent)
      closeComment = FOLMMarketHardCloseComment;
   double warningLevel = (folmPreHardActiveUrgent ? FOLMPreHardWarnActiveClosePoints : 0.0);
   long heldMs = GetTickMs() - trackedEntryMs[idx];
   CaptureRuleTelemetry(ticket, idx, fav, heldMs, "URGENT_RETRY_CLOSE_REQUEST", warningLevel, "URGENT_RETRY");
   if(ClosePositionWithComment(ticket, closeComment, CONT_EXIT_LOSS, 0.0))
   {
      string eventName = "PRE_SPEED_AGAINST_DEFENSE_RETRY_CLOSE";
      if(folmMarketHardUrgent)
         eventName = "FOLM_MARKET_HARD_CAP_RETRY_CLOSE";
      else if(folmSellMarketEarlyUrgent)
         eventName = "FOLM_SELL_MARKET_EARLY_DANGER_RETRY_CLOSE";
      else if(folmPreHardActiveUrgent)
         eventName = FOLMPreHardWarnActiveEventBase() + "_RETRY_CLOSE";
      else if(v40FLXQPressureShieldUrgent)
         eventName = "V40_FLXQ_SELL_STOP_PRESSURE_SHIELD_RETRY_CLOSE";
      else if(v40PreSpeedShieldUrgent)
         eventName = "V40_PRE_SPEED_EXECUTION_SHIELD_RETRY_CLOSE";
      else if(flxqSellStopPressureUrgent)
         eventName = "FLXQ_SELL_STOP_PRESSURE_RETRY_CLOSE";
      if(folmSellMarketEarlyUrgent)
         StartV44FOLMSGhost(ticket, idx, fav, eventName);
      LogInfo(eventName, "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " attempts=" + (string)trackedPreSpeedDefenseAttempts[idx] +
              " folm_market_hard=" + (folmMarketHardUrgent ? "true" : "false") +
              " folm_sell_market_early=" + (folmSellMarketEarlyUrgent ? "true" : "false") +
              " folm_warn24_active=" + (folmPreHardActiveUrgent ? "true" : "false") +
              " v40_pre_speed_shield=" + (v40PreSpeedShieldUrgent ? "true" : "false") +
              " v40_flxq_pressure_shield=" + (v40FLXQPressureShieldUrgent ? "true" : "false") +
              " flxq_sell_stop_pressure=" + (flxqSellStopPressureUrgent ? "true" : "false") +
              " stop_flow_danger=" + (stopFlowDangerUrgent ? "true" : "false") +
              " labels=" + trackedLabels[idx]);
      TrackerRemoveIndex(idx);
      return true;
   }

   if(lastCloseRetcode == SAR_RETCODE_POSITION_CLOSED && !PositionSelectByTicket(ticket))
   {
      string eventName = "PRE_SPEED_AGAINST_DEFENSE_RETRY_RESOLVED_CLOSE";
      if(folmMarketHardUrgent)
         eventName = "FOLM_MARKET_HARD_CAP_RETRY_RESOLVED_CLOSE";
      else if(folmSellMarketEarlyUrgent)
         eventName = "FOLM_SELL_MARKET_EARLY_DANGER_RETRY_RESOLVED_CLOSE";
      else if(folmPreHardActiveUrgent)
         eventName = FOLMPreHardWarnActiveEventBase() + "_RETRY_RESOLVED_CLOSE";
      else if(v40FLXQPressureShieldUrgent)
         eventName = "V40_FLXQ_SELL_STOP_PRESSURE_SHIELD_RETRY_RESOLVED_CLOSE";
      else if(v40PreSpeedShieldUrgent)
         eventName = "V40_PRE_SPEED_EXECUTION_SHIELD_RETRY_RESOLVED_CLOSE";
      else if(flxqSellStopPressureUrgent)
         eventName = "FLXQ_SELL_STOP_PRESSURE_RETRY_RESOLVED_CLOSE";
      double resolvedWarningLevel = (folmPreHardActiveUrgent ? FOLMPreHardWarnActiveClosePoints : 0.0);
      long resolvedHeldMs = GetTickMs() - trackedEntryMs[idx];
      CaptureRuleTelemetry(ticket, idx, TrackedLastKnownFav(idx), resolvedHeldMs, eventName, resolvedWarningLevel, "URGENT_RESOLVED");
      if(folmSellMarketEarlyUrgent)
         StartV44FOLMSGhost(ticket, idx, TrackedLastKnownFav(idx), eventName);
      LogInfo(eventName, "ticket=" + (string)ticket +
              " fav=" + DoubleToString(TrackedLastKnownFav(idx), 1) +
              " attempts=" + (string)trackedPreSpeedDefenseAttempts[idx] +
              " resolved=true last_retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " labels=" + trackedLabels[idx]);
      TrackerRemoveIndex(idx);
      return true;
   }

   long nowMs = GetTickMs();
   if(ShouldLogPreSpeedDefenseRetry(idx, nowMs))
   {
      string eventName = "PRE_SPEED_AGAINST_DEFENSE_RETRY_FAILED";
      if(folmMarketHardUrgent)
         eventName = "FOLM_MARKET_HARD_CAP_RETRY_FAILED";
      else if(folmSellMarketEarlyUrgent)
         eventName = "FOLM_SELL_MARKET_EARLY_DANGER_RETRY_FAILED";
      else if(folmPreHardActiveUrgent)
         eventName = FOLMPreHardWarnActiveEventBase() + "_RETRY_FAILED";
      else if(v40FLXQPressureShieldUrgent)
         eventName = "V40_FLXQ_SELL_STOP_PRESSURE_SHIELD_RETRY_FAILED";
      else if(v40PreSpeedShieldUrgent)
         eventName = "V40_PRE_SPEED_EXECUTION_SHIELD_RETRY_FAILED";
      else if(flxqSellStopPressureUrgent)
         eventName = "FLXQ_SELL_STOP_PRESSURE_RETRY_FAILED";
      LogInfo(eventName, "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " attempts=" + (string)trackedPreSpeedDefenseAttempts[idx] +
              " retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " labels=" + trackedLabels[idx]);
   }
   return false;
}

//+------------------------------------------------------------------+
void MarkRetestCollapseUrgentClose(const ulong ticket, const double fav, const int idx,
                                   const double velocityPtsSec, const double collapseJump,
                                   const long warningAgeMs, const long collapseConfirmMs)
{
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return;

   if(!trackedRetestCollapseUrgentClose[idx])
   {
      trackedRetestCollapseUrgentClose[idx] = true;
      trackedRetestCollapseAttempts[idx] = 0;
      trackedRetestCollapseLastLogMs[idx] = 0;
      trackedUrgentCloseStartMs[idx] = GetTickMs();
      if(StringFind(trackedLabels[idx], "RETEST_COLLAPSE_URGENT") < 0)
         trackedLabels[idx] += ";RETEST_COLLAPSE_URGENT";
      LogInfo("RETEST_COLLAPSE_RETRY_ARMED", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " velocity_pts_sec=" + DoubleToString(velocityPtsSec, 1) +
              " jump_pts=" + DoubleToString(collapseJump, 1) +
              " warning_age_ms=" + (string)warningAgeMs +
              " confirm_ticks_seen=" + (string)trackedRetestCollapseTicks[idx] +
              " confirm_ms_seen=" + (string)collapseConfirmMs +
              " retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " labels=" + trackedLabels[idx]);
   }
}

//+------------------------------------------------------------------+
string RetestUrgentEventBase(const int idx)
{
   if(idx >= 0 && idx < ArraySize(trackedTickets))
   {
      if(TrackedLabelHas(idx, "V40_RETEST_EXECUTION_SHIELD_URGENT"))
         return "V40_RETEST_EXECUTION_SHIELD";
      if(TrackedLabelHas(idx, "NO_FOLLOW_EARLY_URGENT"))
         return "NO_FOLLOW_EARLY";
      if(TrackedLabelHas(idx, "NO_FOLLOW_URGENT"))
         return "NO_FOLLOW";
      if(TrackedLabelHas(idx, "RETEST_FAILED_EARLY_URGENT"))
         return "RETEST_FAILED_EARLY";
      if(TrackedLabelHas(idx, "RETEST_FAILED_URGENT"))
         return "RETEST_FAILED";
   }
   return "RETEST_COLLAPSE";
}

//+------------------------------------------------------------------+
string RetestUrgentCloseComment(const int idx)
{
   string eventBase = RetestUrgentEventBase(idx);
   if(eventBase == "NO_FOLLOW_EARLY")
      return NoFollowEarlyCloseComment;
   if(eventBase == "NO_FOLLOW")
      return NoFollowCloseComment;
   if(eventBase == "RETEST_FAILED_EARLY")
      return RetestFailedEarlyCloseComment;
   if(eventBase == "RETEST_FAILED")
      return RetestFailedCloseComment;
   if(eventBase == "V40_RETEST_EXECUTION_SHIELD")
      return V40RetestExecutionShieldCloseComment;
   return RetestCollapseCloseComment;
}

//+------------------------------------------------------------------+
void MarkRetestStyleUrgentClose(const ulong ticket, const double fav, const int idx,
                                const string urgentLabel, const string armEvent,
                                const string detail)
{
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return;

   if(StringFind(trackedLabels[idx], urgentLabel) < 0)
      trackedLabels[idx] += ";" + urgentLabel;

   if(!trackedRetestCollapseUrgentClose[idx])
   {
      trackedRetestCollapseUrgentClose[idx] = true;
      trackedRetestCollapseAttempts[idx] = 0;
      trackedRetestCollapseLastLogMs[idx] = 0;
      trackedUrgentCloseStartMs[idx] = GetTickMs();
      LogInfo(armEvent, "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " " + detail +
              " retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " labels=" + trackedLabels[idx]);
   }
}

//+------------------------------------------------------------------+
bool TryRetestCollapseUrgentRetry(const ulong ticket, const double fav, const int idx)
{
   if(InpUseContinuationFreeze) return false;
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return false;
   if(!trackedRetestCollapseUrgentClose[idx])
      return false;

   string eventBase = RetestUrgentEventBase(idx);
   string closeComment = RetestUrgentCloseComment(idx);
   TrackerSetLastKnownFav(idx, fav);
   trackedRetestCollapseAttempts[idx]++;
   if(ClosePositionWithComment(ticket, closeComment, CONT_EXIT_LOSS, 0.0))
   {
      LogInfo(eventBase + "_RETRY_CLOSE", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " attempts=" + (string)trackedRetestCollapseAttempts[idx] +
              " labels=" + trackedLabels[idx]);
      TrackerRemoveIndex(idx);
      return true;
   }

   if(lastCloseRetcode == SAR_RETCODE_POSITION_CLOSED && !PositionSelectByTicket(ticket))
   {
      LogInfo(eventBase + "_RETRY_POSITION_GONE", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(TrackedLastKnownFav(idx), 1) +
              " attempts=" + (string)trackedRetestCollapseAttempts[idx] +
              " retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " labels=" + trackedLabels[idx]);
      TrackerRemoveIndex(idx);
      return true;
   }

   long nowMs = GetTickMs();
   if(ShouldLogRetestCollapseRetry(idx, nowMs))
   {
      LogInfo(eventBase + "_RETRY_FAILED", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " attempts=" + (string)trackedRetestCollapseAttempts[idx] +
              " retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " labels=" + trackedLabels[idx]);
   }
   return false;
}

//+------------------------------------------------------------------+
void MarkHardFloorUrgentClose(const ulong ticket, const double fav, const int idx,
                              const bool holdActive, const long holdAgeMs)
{
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return;

   if(!trackedHardFloorUrgentClose[idx])
   {
      trackedHardFloorUrgentClose[idx] = true;
      trackedHardFloorAttempts[idx] = 0;
      trackedHardFloorLastLogMs[idx] = 0;
      trackedUrgentCloseStartMs[idx] = GetTickMs();
      if(StringFind(trackedLabels[idx], "RETEST_HARD_FLOOR_URGENT") < 0)
         trackedLabels[idx] += ";RETEST_HARD_FLOOR_URGENT";
      LogInfo("RETEST_HARD_FLOOR_RETRY_ARMED", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " hard_floor=" + DoubleToString(RetestCollapseHardMaxLossPoints, 1) +
              " hold_active=" + (holdActive ? "true" : "false") +
              " hold_age_ms=" + (string)holdAgeMs +
              " retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " labels=" + trackedLabels[idx]);
   }
}

//+------------------------------------------------------------------+
bool TryHardFloorUrgentRetry(const ulong ticket, const double fav, const int idx)
{
   if(InpUseContinuationFreeze) return false;
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return false;
   if(!trackedHardFloorUrgentClose[idx])
      return false;

   TrackerSetLastKnownFav(idx, fav);
   trackedHardFloorAttempts[idx]++;
   if(ClosePositionWithComment(ticket, RetestCollapseHardCloseComment, CONT_EXIT_LOSS, RetestCollapseHardMaxLossPoints))
   {
      LogInfo("RETEST_HARD_FLOOR_RETRY_CLOSE", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " attempts=" + (string)trackedHardFloorAttempts[idx] +
              " labels=" + trackedLabels[idx]);
      TrackerRemoveIndex(idx);
      return true;
   }

   if(lastCloseRetcode == SAR_RETCODE_POSITION_CLOSED && !PositionSelectByTicket(ticket))
   {
      LogInfo("RETEST_HARD_FLOOR_RETRY_POSITION_GONE", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(TrackedLastKnownFav(idx), 1) +
              " attempts=" + (string)trackedHardFloorAttempts[idx] +
              " retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " labels=" + trackedLabels[idx]);
      TrackerRemoveIndex(idx);
      return true;
   }

   long nowMs = GetTickMs();
   if(ShouldLogHardFloorRetry(idx, nowMs))
   {
      LogInfo("RETEST_HARD_FLOOR_RETRY_FAILED", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " attempts=" + (string)trackedHardFloorAttempts[idx] +
              " retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " labels=" + trackedLabels[idx]);
   }
   return false;
}

//+------------------------------------------------------------------+
double RetestCollapseVelocity(const int idx, const double fav, const long nowMs)
{
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return 0.0;
   if(trackedLastFavMs[idx] <= 0 || nowMs <= trackedLastFavMs[idx])
      return 0.0;

   double dtSec = MathMax(0.001, (double)(nowMs - trackedLastFavMs[idx]) / 1000.0);
   double worseningPts = trackedLastFavs[idx] - fav;
   if(worseningPts <= 0.0)
      return 0.0;

   return worseningPts / dtSec;
}

//+------------------------------------------------------------------+
bool TrackedLabelHas(const int idx, const string needle)
{
   if(idx < 0 || idx >= ArraySize(trackedLabels))
      return false;
   return (StringFind(trackedLabels[idx], needle) >= 0);
}

//+------------------------------------------------------------------+
bool RecentPreSpeedAgainstTrade(const int side, const long nowMs, string &details)
{
   details = "";
   if(side == 0 || preSpeedLastSignalDir == 0 || preSpeedLastSignalMs <= 0)
      return false;
   if(preSpeedLastSignalDir != -side)
      return false;

   if(preSpeedLastSignalLevel >= 70)
   {
      if(!PreSpeedAgainstDefenseCloseOnPreSpeed70)
         return false;
   }
   else
   {
      if(!PreSpeedAgainstDefenseCloseOnPreSpeed50)
         return false;
   }

   long maxAgeMs = (PreSpeedAgainstDefenseMaxSignalAgeMs > 0
                    ? (long)PreSpeedAgainstDefenseMaxSignalAgeMs
                    : (long)MathMax(1, SpeedAlertHoldSeconds + PreSpeedAgainstDefenseNoFollowSeconds) * 1000);
   long ageMs = nowMs - preSpeedLastSignalMs;
   if(ageMs < 0 || ageMs > maxAgeMs)
      return false;

   details = "pre_speed_level=" + (string)preSpeedLastSignalLevel +
             " pre_speed_dir=" + (string)preSpeedLastSignalDir +
             " pre_speed_age_ms=" + (string)ageMs +
             " pre_speed_max_age_ms=" + (string)maxAgeMs +
             " pre_speed_move=" + DoubleToString(preSpeedLastSignalMove, 1) +
             " pre_speed_ratio=" + DoubleToString(preSpeedLastSignalRatio, 2) +
             " v1=" + DoubleToString(preSpeedLastSignalV1, 1) +
             " v3=" + DoubleToString(preSpeedLastSignalV3, 1) +
             " v5=" + DoubleToString(preSpeedLastSignalV5, 1);
   return true;
}

//+------------------------------------------------------------------+
bool TryPreSpeedAgainstDefenseClose(const ulong ticket, const double fav, const int idx, const long heldMs)
{
   if(!UsePreSpeedAgainstDefense)
      return false;
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return false;
   if(trackedHit21s[idx] || trackedHit37s[idx])
      return false;

   bool flxqSellStopFastDefense = (FLXQSellStopFastPreSpeedDefense &&
                                   TrackedLabelHas(idx, "SAR:FLXQ:SS"));
   bool pressure = (trackedMaes[idx] <= -OppositePressurePoints);
   bool flowDisagrees = TrackedLabelHas(idx, ":FD") || TrackedLabelHas(idx, "FLOW_DISAGREES");
   bool v40PreSpeedShield = (UseV40ExecutionShield &&
                             V40PreSpeedExecutionShield &&
                             V40PreSpeedExecutionShieldLossPoints > 0.0 &&
                             fav <= -V40PreSpeedExecutionShieldLossPoints &&
                             (!V40PreSpeedExecutionShieldNeedsPressureOrFlow ||
                              pressure || flowDisagrees));
   double defenseMinLoss = PreSpeedAgainstDefenseMinLossPoints;
   if(flxqSellStopFastDefense && FLXQSellStopFastPreSpeedDefenseLossPoints > 0.0)
      defenseMinLoss = MathMin(defenseMinLoss, FLXQSellStopFastPreSpeedDefenseLossPoints);
   if(v40PreSpeedShield)
      defenseMinLoss = MathMin(defenseMinLoss, V40PreSpeedExecutionShieldLossPoints);
   if(fav > -defenseMinLoss)
      return false;

   bool exhlTrade = TrackedLabelHas(idx, "SAR:EXHL");
   bool exhlPreSpeedDanger = (EXHLPreSpeedDangerClose &&
                              exhlTrade &&
                              EXHLPreSpeedDangerLossPoints > 0.0 &&
                              fav <= -EXHLPreSpeedDangerLossPoints);
   bool folmTrade = TrackedLabelHas(idx, "SAR:FOLM");
   double folmDangerLoss = (flowDisagrees && FOLMFlowDisagreeDangerLossPoints > 0.0
                            ? FOLMFlowDisagreeDangerLossPoints
                            : FOLMMarketDangerLossPoints);
   bool folmMarketDanger = (FOLMMarketDangerClose &&
                            folmTrade &&
                            folmDangerLoss > 0.0 &&
                            fav <= -folmDangerLoss);
   bool flxqSellStopFastHardClose = (flxqSellStopFastDefense &&
                                     FLXQSellStopFastPreSpeedDefenseLossPoints > 0.0 &&
                                     fav <= -FLXQSellStopFastPreSpeedDefenseLossPoints);
   if(PreSpeedAgainstDefenseNeedsOppositePressure && !pressure &&
      !v40PreSpeedShield &&
      !(exhlPreSpeedDanger && !EXHLPreSpeedDangerNeedsOppositePressure) &&
      !(folmMarketDanger && !FOLMMarketDangerNeedsOppositePressure) &&
      !(flxqSellStopFastHardClose && !FLXQSellStopFastPreSpeedDefenseNeedsOppositePressure))
      return false;
   if(exhlPreSpeedDanger && EXHLPreSpeedDangerNeedsOppositePressure && !pressure)
      return false;
   if(folmMarketDanger && FOLMMarketDangerNeedsOppositePressure && !pressure)
      return false;
   if(flxqSellStopFastHardClose && FLXQSellStopFastPreSpeedDefenseNeedsOppositePressure && !pressure)
      return false;

   int waitSeconds = PreSpeedAgainstDefenseNoFollowSeconds;
   if(flxqSellStopFastDefense)
      waitSeconds = FLXQSellStopPreSpeedDefenseNoFollowSeconds;
   bool waitOk = (waitSeconds <= 0 || heldMs >= waitSeconds * 1000);
   bool immediateByFlow = (FlowDisagreeMakesDefenseImmediate && flowDisagrees);
   bool normalHardClose = (PreSpeedAgainstDefenseHardClose &&
                           PreSpeedAgainstDefenseHardMaxLossPoints > 0.0 &&
                           fav <= -PreSpeedAgainstDefenseHardMaxLossPoints);
   bool hardClose = (normalHardClose || flxqSellStopFastHardClose);
   if(!v40PreSpeedShield && !exhlPreSpeedDanger && !folmMarketDanger && !hardClose && !waitOk && !immediateByFlow)
      return false;

   string preSpeedDetails = "";
   long nowMs = GetTickMs();
   if(!RecentPreSpeedAgainstTrade(trackedSides[idx], nowMs, preSpeedDetails))
      return false;

   if(!TrackedLabelHas(idx, "PRE_SPEED_AGAINST"))
      trackedLabels[idx] += ";PRE_SPEED_AGAINST";
   if(v40PreSpeedShield && !TrackedLabelHas(idx, "V40_PRE_SPEED_EXECUTION_SHIELD"))
      trackedLabels[idx] += ";V40_PRE_SPEED_EXECUTION_SHIELD";
   if(exhlPreSpeedDanger && !TrackedLabelHas(idx, "EXHL_PRE_SPEED_DANGER"))
      trackedLabels[idx] += ";EXHL_PRE_SPEED_DANGER";
   if(folmMarketDanger && !TrackedLabelHas(idx, "FOLM_MARKET_DANGER"))
      trackedLabels[idx] += ";FOLM_MARKET_DANGER";
   if(hardClose && !TrackedLabelHas(idx, "PRE_SPEED_HARD_FLOOR"))
      trackedLabels[idx] += ";PRE_SPEED_HARD_FLOOR";
   if(flxqSellStopFastHardClose && !TrackedLabelHas(idx, "FLXQ_FAST_PRE_SPEED_HARD"))
      trackedLabels[idx] += ";FLXQ_FAST_PRE_SPEED_HARD";
   if(pressure && !TrackedLabelHas(idx, "OPPOSITE_PRESSURE"))
      trackedLabels[idx] += ";OPPOSITE_PRESSURE";
   if(flowDisagrees && !TrackedLabelHas(idx, "FLOW_DISAGREES"))
      trackedLabels[idx] += ";FLOW_DISAGREES";

   string hardDetails = " hard_close=" + (hardClose ? "true" : "false") +
                        " hard_max_loss=" + DoubleToString(PreSpeedAgainstDefenseHardMaxLossPoints, 1) +
                        " normal_hard_close=" + (normalHardClose ? "true" : "false") +
                        " flxq_fast_hard_close=" + (flxqSellStopFastHardClose ? "true" : "false") +
                        " flxq_fast_loss=" + DoubleToString(FLXQSellStopFastPreSpeedDefenseLossPoints, 1) +
                        " flxq_fast_needs_pressure=" + (FLXQSellStopFastPreSpeedDefenseNeedsOppositePressure ? "true" : "false") +
                        " v40_pre_speed_shield=" + (v40PreSpeedShield ? "true" : "false") +
                        " v40_pre_speed_loss=" + DoubleToString(V40PreSpeedExecutionShieldLossPoints, 1) +
                        " exhl_danger=" + (exhlPreSpeedDanger ? "true" : "false") +
                        " exhl_danger_loss=" + DoubleToString(EXHLPreSpeedDangerLossPoints, 1) +
                        " folm_danger=" + (folmMarketDanger ? "true" : "false") +
                        " folm_danger_loss=" + DoubleToString(folmDangerLoss, 1);
   string closeEvent = (v40PreSpeedShield
                        ? "V40_PRE_SPEED_EXECUTION_SHIELD_CLOSE"
                        : (exhlPreSpeedDanger
                        ? "EXHL_PRE_SPEED_DANGER_CLOSE"
                        : (folmMarketDanger
                           ? "FOLM_MARKET_DANGER_CLOSE"
                           : (flxqSellStopFastHardClose
                              ? "FLXQ_SELL_STOP_FAST_PRE_SPEED_CLOSE"
                              : (hardClose
                           ? "PRE_SPEED_AGAINST_DEFENSE_HARD_CLOSE"
                                 : "PRE_SPEED_AGAINST_DEFENSE_CLOSE")))));
   if(v40PreSpeedShield)
      PrimeActiveCloseTelemetry(ticket, idx, fav, heldMs, closeEvent,
                                V40PreSpeedExecutionShieldLossPoints, "V40_PRE_SPEED_EXECUTION_SHIELD");
   string closeComment = (v40PreSpeedShield
                          ? V40PreSpeedExecutionShieldCloseComment
                          : PreSpeedAgainstDefenseCloseComment);
   double closeLossBoundary=MathMax(0.0,defenseMinLoss);
   if(v40PreSpeedShield) closeLossBoundary=MathMax(closeLossBoundary,V40PreSpeedExecutionShieldLossPoints);
   else if(exhlPreSpeedDanger) closeLossBoundary=MathMax(closeLossBoundary,EXHLPreSpeedDangerLossPoints);
   else if(folmMarketDanger) closeLossBoundary=MathMax(closeLossBoundary,folmDangerLoss);
   else if(flxqSellStopFastHardClose) closeLossBoundary=MathMax(closeLossBoundary,FLXQSellStopFastPreSpeedDefenseLossPoints);
   else if(hardClose) closeLossBoundary=MathMax(closeLossBoundary,PreSpeedAgainstDefenseHardMaxLossPoints);
   if(ClosePositionWithComment(ticket, closeComment, CONT_EXIT_LOSS, closeLossBoundary))
   {
      LogInfo(closeEvent, "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " held_ms=" + (string)heldMs +
              " wait_seconds=" + (string)waitSeconds +
              " flxq_sell_stop_fast=" + (flxqSellStopFastDefense ? "true" : "false") +
              " flow_disagrees=" + (flowDisagrees ? "true" : "false") +
              " immediate_by_flow=" + (immediateByFlow ? "true" : "false") +
              hardDetails +
              " " + preSpeedDetails +
              " labels=" + trackedLabels[idx]);
      TrackerRemoveIndex(idx);
      return true;
   }

   if(lastCloseRetcode == SAR_RETCODE_FROZEN)
   {
      if(v40PreSpeedShield && !TrackedLabelHas(idx, "V40_PRE_SPEED_SHIELD_URGENT"))
         trackedLabels[idx] += ";V40_PRE_SPEED_SHIELD_URGENT";
      MarkPreSpeedDefenseUrgentClose(ticket, fav, idx, heldMs, flowDisagrees, immediateByFlow,
                                     preSpeedDetails + hardDetails, waitSeconds, flxqSellStopFastDefense, false);
      return true;
   }

   if(lastCloseRetcode == SAR_RETCODE_POSITION_CLOSED && !PositionSelectByTicket(ticket))
   {
      LogInfo("PRE_SPEED_AGAINST_DEFENSE_POSITION_GONE", "ticket=" + (string)ticket +
             " fav=" + DoubleToString(fav, 1) +
             " held_ms=" + (string)heldMs +
             " wait_seconds=" + (string)waitSeconds +
             " flxq_sell_stop_fast=" + (flxqSellStopFastDefense ? "true" : "false") +
             " retcode=" + (string)lastCloseRetcode +
             " " + lastCloseRetcodeDescription +
             hardDetails +
             " " + preSpeedDetails +
              " labels=" + trackedLabels[idx]);
      TrackerRemoveIndex(idx);
      return true;
   }

   LogInfo((v40PreSpeedShield
            ? "V40_PRE_SPEED_EXECUTION_SHIELD_CLOSE_FAILED"
            : (exhlPreSpeedDanger
            ? "EXHL_PRE_SPEED_DANGER_CLOSE_FAILED"
            : (folmMarketDanger
               ? "FOLM_MARKET_DANGER_CLOSE_FAILED"
               : (hardClose
                  ? "PRE_SPEED_AGAINST_DEFENSE_HARD_CLOSE_FAILED"
                  : "PRE_SPEED_AGAINST_DEFENSE_CLOSE_FAILED")))), "ticket=" + (string)ticket +
           " fav=" + DoubleToString(fav, 1) +
           " held_ms=" + (string)heldMs +
           " wait_seconds=" + (string)waitSeconds +
           " flxq_sell_stop_fast=" + (flxqSellStopFastDefense ? "true" : "false") +
           " retcode=" + (string)lastCloseRetcode +
           " " + lastCloseRetcodeDescription +
           hardDetails +
           " " + preSpeedDetails +
           " labels=" + trackedLabels[idx]);
   return false;
}

//+------------------------------------------------------------------+
bool TryFOLMSellMarketEarlyDangerClose(const ulong ticket, const double fav, const int idx, const long heldMs)
{
   if(!FOLMSellMarketEarlyDangerClose)
      return false;
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return false;
   if(!TrackedLabelHas(idx, "SAR:FOLM:SM"))
      return false;
   if(FOLMSellMarketEarlyDangerLossPoints <= 0.0 ||
      fav > -FOLMSellMarketEarlyDangerLossPoints)
      return false;

   bool pressure = (trackedMaes[idx] <= -OppositePressurePoints);
   if(FOLMSellMarketEarlyDangerNeedsOppositePressure && !pressure)
      return false;

   bool flowDisagrees = TrackedLabelHas(idx, ":FD") || TrackedLabelHas(idx, "FLOW_DISAGREES");
   if(!TrackedLabelHas(idx, "FOLM_SM_EARLY_DANGER"))
      trackedLabels[idx] += ";FOLM_SM_EARLY_DANGER";
   if(pressure && !TrackedLabelHas(idx, "OPPOSITE_PRESSURE"))
      trackedLabels[idx] += ";OPPOSITE_PRESSURE";
   if(flowDisagrees && !TrackedLabelHas(idx, "FLOW_DISAGREES"))
      trackedLabels[idx] += ";FLOW_DISAGREES";

   string dangerDetails = "folm_sell_market_early=true" +
                          " danger_loss=" + DoubleToString(FOLMSellMarketEarlyDangerLossPoints, 1) +
                          " pressure=" + (pressure ? "true" : "false") +
                          " needs_pressure=" + (FOLMSellMarketEarlyDangerNeedsOppositePressure ? "true" : "false") +
                          " mae=" + DoubleToString(trackedMaes[idx], 1) +
                          " hit21=" + (trackedHit21s[idx] ? "true" : "false") +
                          " hit37=" + (trackedHit37s[idx] ? "true" : "false") +
                          " flow_disagrees=" + (flowDisagrees ? "true" : "false");

   if(ClosePositionWithComment(ticket, FOLMSellMarketEarlyDangerCloseComment, CONT_EXIT_LOSS, FOLMSellMarketEarlyDangerLossPoints))
   {
      CaptureRuleTelemetry(ticket, idx, fav, heldMs, "FOLM_SELL_MARKET_EARLY_DANGER_CLOSE", 0.0, "FOLM_SM_GHOST");
      StartV44FOLMSGhost(ticket, idx, fav, "FOLM_SELL_MARKET_EARLY_DANGER_CLOSE");
      LogInfo("FOLM_SELL_MARKET_EARLY_DANGER_CLOSE", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " held_ms=" + (string)heldMs +
              " " + dangerDetails +
              " labels=" + trackedLabels[idx]);
      TrackerRemoveIndex(idx);
      return true;
   }

   if(lastCloseRetcode == SAR_RETCODE_FROZEN)
   {
      if(!TrackedLabelHas(idx, "FOLM_SM_EARLY_URGENT"))
         trackedLabels[idx] += ";FOLM_SM_EARLY_URGENT";
      MarkPreSpeedDefenseUrgentClose(ticket, fav, idx, heldMs, flowDisagrees, false,
                                     dangerDetails, 0, false, false);
      return true;
   }

   if(lastCloseRetcode == SAR_RETCODE_POSITION_CLOSED && !PositionSelectByTicket(ticket))
   {
      CaptureRuleTelemetry(ticket, idx, fav, heldMs, "FOLM_SELL_MARKET_EARLY_DANGER_POSITION_GONE", 0.0, "FOLM_SM_GHOST");
      StartV44FOLMSGhost(ticket, idx, fav, "FOLM_SELL_MARKET_EARLY_DANGER_POSITION_GONE");
      LogInfo("FOLM_SELL_MARKET_EARLY_DANGER_POSITION_GONE", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " held_ms=" + (string)heldMs +
              " retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " " + dangerDetails +
              " labels=" + trackedLabels[idx]);
      TrackerRemoveIndex(idx);
      return true;
   }

   LogInfo("FOLM_SELL_MARKET_EARLY_DANGER_CLOSE_FAILED", "ticket=" + (string)ticket +
           " fav=" + DoubleToString(fav, 1) +
           " held_ms=" + (string)heldMs +
           " retcode=" + (string)lastCloseRetcode +
           " " + lastCloseRetcodeDescription +
           " " + dangerDetails +
           " labels=" + trackedLabels[idx]);
   return false;
}

//+------------------------------------------------------------------+
bool TryFOLMMarketHardCapClose(const ulong ticket, const double fav, const int idx, const long heldMs)
{
   if(!FOLMMarketHardClose)
      return false;
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return false;
   if(!TrackedLabelHas(idx, "SAR:FOLM"))
      return false;
   if(FOLMMarketHardMaxLossPoints <= 0.0 || fav > -FOLMMarketHardMaxLossPoints)
      return false;

   if(!TrackedLabelHas(idx, "FOLM_MARKET_HARD_CAP"))
      trackedLabels[idx] += ";FOLM_MARKET_HARD_CAP";

   if(ClosePositionWithComment(ticket, FOLMMarketHardCloseComment, CONT_EXIT_LOSS, FOLMMarketHardMaxLossPoints))
   {
      LogInfo("FOLM_MARKET_HARD_CAP_CLOSE", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " held_ms=" + (string)heldMs +
              " hard_max_loss=" + DoubleToString(FOLMMarketHardMaxLossPoints, 1) +
              " labels=" + trackedLabels[idx]);
      TrackerRemoveIndex(idx);
      return true;
   }

   if(lastCloseRetcode == SAR_RETCODE_FROZEN)
   {
      trackedPreSpeedDefenseUrgentClose[idx] = true;
      trackedPreSpeedDefenseAttempts[idx] = 0;
      trackedPreSpeedDefenseLastLogMs[idx] = 0;
      if(!TrackedLabelHas(idx, "FOLM_MARKET_HARD_URGENT"))
         trackedLabels[idx] += ";FOLM_MARKET_HARD_URGENT";
      LogInfo("FOLM_MARKET_HARD_CAP_RETRY_ARMED", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " held_ms=" + (string)heldMs +
              " hard_max_loss=" + DoubleToString(FOLMMarketHardMaxLossPoints, 1) +
              " retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " labels=" + trackedLabels[idx]);
      return true;
   }

   if(lastCloseRetcode == SAR_RETCODE_POSITION_CLOSED && !PositionSelectByTicket(ticket))
   {
      ClearTradeMeasurementContext();
      LogInfo("FOLM_MARKET_HARD_CAP_POSITION_GONE", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " held_ms=" + (string)heldMs +
              " hard_max_loss=" + DoubleToString(FOLMMarketHardMaxLossPoints, 1) +
              " resolved=true last_retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " labels=" + trackedLabels[idx]);
      TrackerRemoveIndex(idx);
      return true;
   }

   LogInfo("FOLM_MARKET_HARD_CAP_CLOSE_FAILED", "ticket=" + (string)ticket +
           " fav=" + DoubleToString(fav, 1) +
           " held_ms=" + (string)heldMs +
           " hard_max_loss=" + DoubleToString(FOLMMarketHardMaxLossPoints, 1) +
           " retcode=" + (string)lastCloseRetcode +
           " " + lastCloseRetcodeDescription +
           " labels=" + trackedLabels[idx]);
   return false;
}

//+------------------------------------------------------------------+
bool TryStopFlowDisagreeDangerClose(const ulong ticket, const double fav, const int idx, const long heldMs)
{
   if(!UseStopFlowDisagreeDangerClose)
      return false;
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return false;

   bool flxqBuyStop = TrackedLabelHas(idx, "SAR:FLXQ:BS");
   bool contBuyStop = TrackedLabelHas(idx, "SAR:CONT:BS");
   bool flxqSellStop = TrackedLabelHas(idx, "SAR:FLXQ:SS");
   bool contSellStop = TrackedLabelHas(idx, "SAR:CONT:SS");
   if(!flxqBuyStop && !contBuyStop && !flxqSellStop && !contSellStop)
      return false;

   bool flowDisagrees = TrackedLabelHas(idx, ":FD") || TrackedLabelHas(idx, "FLOW_DISAGREES");
   if(!flowDisagrees)
      return false;
   if(StopFlowDisagreeDangerLossPoints > 0.0 && fav > -StopFlowDisagreeDangerLossPoints)
      return false;
   if(StopFlowDisagreeDangerMinHoldMs > 0 && heldMs < StopFlowDisagreeDangerMinHoldMs)
      return false;

   bool pressure = (trackedMaes[idx] <= -OppositePressurePoints);
   if(StopFlowDisagreeDangerNeedsOppositePressure && !pressure)
      return false;

   if(!TrackedLabelHas(idx, "STOP_FLOW_DANGER"))
      trackedLabels[idx] += ";STOP_FLOW_DANGER";
   if(!TrackedLabelHas(idx, "FLOW_DISAGREES"))
      trackedLabels[idx] += ";FLOW_DISAGREES";
   if(pressure && !TrackedLabelHas(idx, "OPPOSITE_PRESSURE"))
      trackedLabels[idx] += ";OPPOSITE_PRESSURE";

   string stopDirection = (flxqBuyStop || contBuyStop ? "BUY_STOP" : "SELL_STOP");
   string dangerDetails = "stop_flow_danger=true" +
                          " stop_direction=" + stopDirection +
                          " danger_loss=" + DoubleToString(StopFlowDisagreeDangerLossPoints, 1) +
                          " min_hold_ms=" + (string)StopFlowDisagreeDangerMinHoldMs +
                          " pressure=" + (pressure ? "true" : "false") +
                          " flxq_buy_stop=" + (flxqBuyStop ? "true" : "false") +
                          " cont_buy_stop=" + (contBuyStop ? "true" : "false") +
                          " flxq_sell_stop_fast=" + (flxqSellStop ? "true" : "false") +
                          " cont_sell_stop=" + (contSellStop ? "true" : "false");

   if(ClosePositionWithComment(ticket, StopFlowDisagreeDangerCloseComment, CONT_EXIT_LOSS, MathMax(0.0,StopFlowDisagreeDangerLossPoints)))
   {
      LogInfo("STOP_FLOW_DISAGREE_DANGER_CLOSE", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " held_ms=" + (string)heldMs +
              " " + dangerDetails +
              " labels=" + trackedLabels[idx]);
      TrackerRemoveIndex(idx);
      return true;
   }

   if(lastCloseRetcode == SAR_RETCODE_FROZEN)
   {
      MarkPreSpeedDefenseUrgentClose(ticket, fav, idx, heldMs, flowDisagrees, true,
                                     dangerDetails, 0, flxqSellStop, true);
      return true;
   }

   if(lastCloseRetcode == SAR_RETCODE_POSITION_CLOSED && !PositionSelectByTicket(ticket))
   {
      LogInfo("STOP_FLOW_DISAGREE_DANGER_POSITION_GONE", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " held_ms=" + (string)heldMs +
              " retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " " + dangerDetails +
              " labels=" + trackedLabels[idx]);
      TrackerRemoveIndex(idx);
      return true;
   }

   LogInfo("STOP_FLOW_DISAGREE_DANGER_CLOSE_FAILED", "ticket=" + (string)ticket +
           " fav=" + DoubleToString(fav, 1) +
           " held_ms=" + (string)heldMs +
           " retcode=" + (string)lastCloseRetcode +
           " " + lastCloseRetcodeDescription +
           " " + dangerDetails +
           " labels=" + trackedLabels[idx]);
   return false;
}

//+------------------------------------------------------------------+
bool TryFLXQSellStopPressureDangerClose(const ulong ticket, const double fav, const int idx, const long heldMs)
{
   if(!FLXQSellStopPressureDangerClose)
      return false;
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return false;
   if(!TrackedLabelHas(idx, "SAR:FLXQ:SS"))
      return false;

   bool pressure = (trackedMaes[idx] <= -OppositePressurePoints);
   bool v40Shield = (UseV40ExecutionShield &&
                     V40FLXQSellStopPressureShield &&
                     V40FLXQSellStopPressureShieldLossPoints > 0.0 &&
                     fav <= -V40FLXQSellStopPressureShieldLossPoints &&
                     (!V40FLXQSellStopPressureShieldNeedsPressure || pressure));
   bool normalDanger = (FLXQSellStopPressureDangerLossPoints > 0.0 &&
                        fav <= -FLXQSellStopPressureDangerLossPoints);
   if(!v40Shield && !normalDanger)
      return false;
   if(!pressure && (!v40Shield || V40FLXQSellStopPressureShieldNeedsPressure))
      return false;

   bool flowDisagrees = TrackedLabelHas(idx, ":FD") || TrackedLabelHas(idx, "FLOW_DISAGREES");
   if(v40Shield && !TrackedLabelHas(idx, "V40_FLXQ_SS_PRESSURE_SHIELD"))
      trackedLabels[idx] += ";V40_FLXQ_SS_PRESSURE_SHIELD";
   if(normalDanger && !TrackedLabelHas(idx, "FLXQ_SS_PRESSURE_DANGER"))
      trackedLabels[idx] += ";FLXQ_SS_PRESSURE_DANGER";
   if(!TrackedLabelHas(idx, "OPPOSITE_PRESSURE"))
      trackedLabels[idx] += ";OPPOSITE_PRESSURE";
   if(flowDisagrees && !TrackedLabelHas(idx, "FLOW_DISAGREES"))
      trackedLabels[idx] += ";FLOW_DISAGREES";

   string dangerDetails = "flxq_sell_stop_pressure=true" +
                          " danger_loss=" + DoubleToString(FLXQSellStopPressureDangerLossPoints, 1) +
                          " v40_shield=" + (v40Shield ? "true" : "false") +
                          " v40_shield_loss=" + DoubleToString(V40FLXQSellStopPressureShieldLossPoints, 1) +
                          " pressure=true" +
                          " mae=" + DoubleToString(trackedMaes[idx], 1) +
                          " hit21=" + (trackedHit21s[idx] ? "true" : "false") +
                          " hit37=" + (trackedHit37s[idx] ? "true" : "false") +
                          " flow_disagrees=" + (flowDisagrees ? "true" : "false");

   string eventName = (v40Shield
                       ? "V40_FLXQ_SELL_STOP_PRESSURE_SHIELD_CLOSE"
                       : "FLXQ_SELL_STOP_PRESSURE_CLOSE");
   string closeComment = (v40Shield
                          ? V40FLXQSellStopPressureShieldCloseComment
                          : FLXQSellStopPressureDangerCloseComment);
   double warningLevel = (v40Shield
                          ? V40FLXQSellStopPressureShieldLossPoints
                          : FLXQSellStopPressureDangerLossPoints);
   PrimeActiveCloseTelemetry(ticket, idx, fav, heldMs, eventName,
                             warningLevel, "V40_FLXQ_SELL_STOP_PRESSURE");

   if(ClosePositionWithComment(ticket, closeComment, CONT_EXIT_LOSS, (v40Shield ? V40FLXQSellStopPressureShieldLossPoints : FLXQSellStopPressureDangerLossPoints)))
   {
      LogInfo(eventName, "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " held_ms=" + (string)heldMs +
              " " + dangerDetails +
              " labels=" + trackedLabels[idx]);
      TrackerRemoveIndex(idx);
      return true;
   }

   if(lastCloseRetcode == SAR_RETCODE_FROZEN)
   {
      if(v40Shield && !TrackedLabelHas(idx, "V40_FLXQ_SS_PRESSURE_SHIELD_URGENT"))
         trackedLabels[idx] += ";V40_FLXQ_SS_PRESSURE_SHIELD_URGENT";
      if(!v40Shield && !TrackedLabelHas(idx, "FLXQ_SS_PRESSURE_URGENT"))
         trackedLabels[idx] += ";FLXQ_SS_PRESSURE_URGENT";
      MarkPreSpeedDefenseUrgentClose(ticket, fav, idx, heldMs, flowDisagrees, false,
                                     dangerDetails, 0, true, false);
      return true;
   }

   if(lastCloseRetcode == SAR_RETCODE_POSITION_CLOSED && !PositionSelectByTicket(ticket))
   {
      LogInfo((v40Shield ? "V40_FLXQ_SELL_STOP_PRESSURE_SHIELD_POSITION_GONE" : "FLXQ_SELL_STOP_PRESSURE_POSITION_GONE"), "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " held_ms=" + (string)heldMs +
              " retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " " + dangerDetails +
              " labels=" + trackedLabels[idx]);
      TrackerRemoveIndex(idx);
      return true;
   }

   LogInfo((v40Shield ? "V40_FLXQ_SELL_STOP_PRESSURE_SHIELD_CLOSE_FAILED" : "FLXQ_SELL_STOP_PRESSURE_CLOSE_FAILED"), "ticket=" + (string)ticket +
           " fav=" + DoubleToString(fav, 1) +
           " held_ms=" + (string)heldMs +
           " retcode=" + (string)lastCloseRetcode +
           " " + lastCloseRetcodeDescription +
           " " + dangerDetails +
           " labels=" + trackedLabels[idx]);
   return false;
}

//+------------------------------------------------------------------+
double PassiveWarningLevelByIndex(const int index)
{
   if(index == 0)
      return PassiveWarnLevel1Points;
   if(index == 1)
      return PassiveWarnLevel2Points;
   if(index == 2)
      return PassiveWarnLevel3Points;
   if(index == 3)
      return PassiveWarnLevel4Points;
   return 0.0;
}

//+------------------------------------------------------------------+
int PassiveWarningBitByIndex(const int index)
{
   if(index == 0)
      return 1;
   if(index == 1)
      return 2;
   if(index == 2)
      return 4;
   if(index == 3)
      return 8;
   return 0;
}

//+------------------------------------------------------------------+
string PassiveWarningLevelText(const double level)
{
   return IntegerToString((int)MathRound(level));
}

//+------------------------------------------------------------------+
string PassiveWarningDetails(const int idx, const double fav, const long heldMs, const double level)
{
   bool pressure = (idx >= 0 && idx < ArraySize(trackedMaes) && trackedMaes[idx] <= -OppositePressurePoints);
   bool flowDisagrees = (idx >= 0 && (TrackedLabelHas(idx, ":FD") || TrackedLabelHas(idx, "FLOW_DISAGREES")));
   long nowMs = GetTickMs();
   string preSpeedDetails = " pre_speed_seen=false";
   if(preSpeedLastSignalMs > 0)
   {
      preSpeedDetails = " pre_speed_seen=true" +
                        StringFormat(" pre_speed_level=%d pre_speed_dir=%d pre_speed_age_ms=%d",
                                     preSpeedLastSignalLevel,
                                     preSpeedLastSignalDir,
                                     (int)(nowMs - preSpeedLastSignalMs)) +
                        " pre_speed_move=" + DoubleToString(preSpeedLastSignalMove, 1) +
                        " pre_speed_ratio=" + DoubleToString(preSpeedLastSignalRatio, 2) +
                        " v1=" + DoubleToString(preSpeedLastSignalV1, 1) +
                        " v3=" + DoubleToString(preSpeedLastSignalV3, 1) +
                        " v5=" + DoubleToString(preSpeedLastSignalV5, 1);
   }

   string details = "fav=" + DoubleToString(fav, 1) +
                    " warning_level=" + DoubleToString(level, 1) +
                    " held_ms=" + (string)heldMs +
                    " would_soft_close=true" +
                    " hit21=" + ((idx >= 0 && trackedHit21s[idx]) ? "true" : "false") +
                    " hit37=" + ((idx >= 0 && trackedHit37s[idx]) ? "true" : "false") +
                    " pressure=" + (pressure ? "true" : "false") +
                    " flow_disagrees=" + (flowDisagrees ? "true" : "false") +
                    " mfe=" + ((idx >= 0) ? DoubleToString(trackedMfes[idx], 1) : "0.0") +
                    " mae=" + ((idx >= 0) ? DoubleToString(trackedMaes[idx], 1) : "0.0") +
                    " first10s_mfe=" + ((idx >= 0) ? DoubleToString(trackedFirst10sMfes[idx], 1) : "0.0") +
                    preSpeedDetails;
   return details;
}

//+------------------------------------------------------------------+
void RecordFOLMWarningTiming(const int idx, const double level, const long heldMs)
{
   if(!UseV41FOLMTickGapTelemetry)
      return;
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return;

   int roundedLevel = (int)MathRound(level);
   if(roundedLevel == 15 && trackedFOLMWarn15Ms[idx] <= 0)
      trackedFOLMWarn15Ms[idx] = heldMs;
   else if(roundedLevel == 18 && trackedFOLMWarn18Ms[idx] <= 0)
      trackedFOLMWarn18Ms[idx] = heldMs;
   else if(roundedLevel == 21 && trackedFOLMWarn21Ms[idx] <= 0)
      trackedFOLMWarn21Ms[idx] = heldMs;
   else if(roundedLevel == 24)
   {
      if(trackedFOLMWarn24Ms[idx] <= 0)
         trackedFOLMWarn24Ms[idx] = heldMs;
      if(trackedFOLMWarn24Ticks[idx] <= 0)
         trackedFOLMWarn24Ticks[idx] = trackedTickCounts[idx];
   }
}

//+------------------------------------------------------------------+
void RecordWarningJumpAgainstTrade(const int idx, const double level)
{
   if(!UseV43EarlyJumpTelemetry)
      return;
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return;

   int flag = (trackedLastTickDeltaPts[idx] > 0.1 ? 1 : 0);
   int roundedLevel = (int)MathRound(level);
   if(roundedLevel == 15 && trackedPreWarn15JumpAgainstTrades[idx] < 0)
      trackedPreWarn15JumpAgainstTrades[idx] = flag;
   else if(roundedLevel == 18 && trackedPreWarn18JumpAgainstTrades[idx] < 0)
      trackedPreWarn18JumpAgainstTrades[idx] = flag;
   else if(roundedLevel == 21 && trackedPreWarn21JumpAgainstTrades[idx] < 0)
      trackedPreWarn21JumpAgainstTrades[idx] = flag;
   else if(roundedLevel == 24 && trackedPreWarn24JumpAgainstTrades[idx] < 0)
      trackedPreWarn24JumpAgainstTrades[idx] = flag;
}

//+------------------------------------------------------------------+
void LogPassiveWarningEvent(const ulong ticket,
                            const double fav,
                            const int idx,
                            const long heldMs,
                            const string family,
                            const double level)
{
   string levelText = PassiveWarningLevelText(level);
   string eventName = family + "_WARN_" + levelText;
   CaptureRuleTelemetry(ticket, idx, fav, heldMs, eventName, level, family);
   LogInfo(eventName, "ticket=" + (string)ticket +
           " " + PassiveWarningDetails(idx, fav, heldMs, level) +
           " labels=" + trackedLabels[idx]);
}

//+------------------------------------------------------------------+
void LogPassiveWarningTelemetry(const ulong ticket, const double fav, const int idx, const long heldMs)
{
   if(!UsePassiveWarningTelemetry)
      return;
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return;

   bool isFOLM = TrackedLabelHas(idx, "SAR:FOLM");
   bool retestCandidate = (trackedHit21s[idx] || trackedRetestFaileds[idx] || TrackedLabelHas(idx, "RETEST_FAIL_WARNING"));

   for(int levelIndex = 0; levelIndex < 4; levelIndex++)
   {
      double level = PassiveWarningLevelByIndex(levelIndex);
      int bit = PassiveWarningBitByIndex(levelIndex);
      if(level <= 0.0 || bit <= 0)
         continue;
      if(fav > -level)
         continue;

      if(LogFOLMPreHardWarnings && isFOLM && (trackedFOLMPreHardWarningMasks[idx] & bit) == 0)
      {
         trackedFOLMPreHardWarningMasks[idx] = trackedFOLMPreHardWarningMasks[idx] | bit;
         RecordFOLMWarningTiming(idx, level, heldMs);
         RecordWarningJumpAgainstTrade(idx, level);
         LogPassiveWarningEvent(ticket, fav, idx, heldMs, "FOLM_PRE_HARD", level);
      }

      if(LogRetestPreFailWarnings && retestCandidate && (trackedRetestPreFailWarningMasks[idx] & bit) == 0)
      {
         trackedRetestPreFailWarningMasks[idx] = trackedRetestPreFailWarningMasks[idx] | bit;
         RecordWarningJumpAgainstTrade(idx, level);
         LogPassiveWarningEvent(ticket, fav, idx, heldMs, "RETEST_PRE_FAIL", level);
      }
   }
}

//+------------------------------------------------------------------+
bool TryFOLMPreHardWarnActiveClose(const ulong ticket, const double fav, const int idx, const long heldMs)
{
   if(!UseFOLMPreHardWarnActiveClose)
      return false;
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return false;
   if(!TrackedLabelHas(idx, "SAR:FOLM"))
      return false;
   if(FOLMPreHardWarnActiveClosePoints <= 0.0 || fav > -FOLMPreHardWarnActiveClosePoints)
      return false;

   string eventBase = FOLMPreHardWarnActiveEventBase();
   if(!TrackedLabelHas(idx, "FOLM_PRE_HARD_WARN_24_ACTIVE"))
      trackedLabels[idx] += ";FOLM_PRE_HARD_WARN_24_ACTIVE";

   PrimeActiveCloseTelemetry(ticket, idx, fav, heldMs, eventBase + "_CLOSE",
                             FOLMPreHardWarnActiveClosePoints, "FOLM_PRE_HARD_ACTIVE");
   if(ClosePositionWithComment(ticket, FOLMPreHardWarnActiveCloseComment, CONT_EXIT_LOSS, FOLMPreHardWarnActiveClosePoints))
   {
      LogInfo(eventBase + "_CLOSE", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " held_ms=" + (string)heldMs +
              " active_level=" + DoubleToString(FOLMPreHardWarnActiveClosePoints, 1) +
              " labels=" + trackedLabels[idx]);
      TrackerRemoveIndex(idx);
      return true;
   }

   if(lastCloseRetcode == SAR_RETCODE_FROZEN)
   {
      trackedPreSpeedDefenseUrgentClose[idx] = true;
      trackedPreSpeedDefenseAttempts[idx] = 0;
      trackedPreSpeedDefenseLastLogMs[idx] = 0;
      trackedUrgentCloseStartMs[idx] = GetTickMs();
      if(!TrackedLabelHas(idx, "FOLM_PRE_HARD_ACTIVE_URGENT"))
         trackedLabels[idx] += ";FOLM_PRE_HARD_ACTIVE_URGENT";
      LogInfo(eventBase + "_RETRY_ARMED", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " held_ms=" + (string)heldMs +
              " active_level=" + DoubleToString(FOLMPreHardWarnActiveClosePoints, 1) +
              " retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " labels=" + trackedLabels[idx]);
      return true;
   }

   if(lastCloseRetcode == SAR_RETCODE_POSITION_CLOSED && !PositionSelectByTicket(ticket))
   {
      PrimeActiveCloseTelemetry(ticket, idx, fav, heldMs, eventBase + "_POSITION_GONE",
                                FOLMPreHardWarnActiveClosePoints, "FOLM_PRE_HARD_ACTIVE");
      LogInfo(eventBase + "_POSITION_GONE", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " held_ms=" + (string)heldMs +
              " active_level=" + DoubleToString(FOLMPreHardWarnActiveClosePoints, 1) +
              " resolved=true last_retcode=" + (string)lastCloseRetcode +
              " " + lastCloseRetcodeDescription +
              " labels=" + trackedLabels[idx]);
      TrackerRemoveIndex(idx);
      return true;
   }

   LogInfo(eventBase + "_CLOSE_FAILED", "ticket=" + (string)ticket +
           " fav=" + DoubleToString(fav, 1) +
           " held_ms=" + (string)heldMs +
           " active_level=" + DoubleToString(FOLMPreHardWarnActiveClosePoints, 1) +
           " retcode=" + (string)lastCloseRetcode +
           " " + lastCloseRetcodeDescription +
           " labels=" + trackedLabels[idx]);
   return false;
}

//+------------------------------------------------------------------+
void ValidatePosition(const ulong ticket, const double fav, const int idx)
{
   if(idx < 0 || idx >= ArraySize(trackedTickets))
      return;

   long heldMs = GetTickMs() - trackedEntryMs[idx];
   LogPassiveWarningTelemetry(ticket, fav, idx, heldMs);

   if(TryFOLMSellMarketEarlyDangerClose(ticket, fav, idx, heldMs))
      return;

   if(TryFOLMPreHardWarnActiveClose(ticket, fav, idx, heldMs))
      return;

   if(TryFOLMMarketHardCapClose(ticket, fav, idx, heldMs))
      return;

   if(TryFLXQSellStopPressureDangerClose(ticket, fav, idx, heldMs))
      return;

   if(TryStopFlowDisagreeDangerClose(ticket, fav, idx, heldMs))
      return;

   if(trackedHit21s[idx] && !trackedRetestHelds[idx] && fav >= 0.0)
   {
      trackedRetestHelds[idx] = true;
      trackedLabels[idx] += ";RETEST_HELD";
      LogInfo("RETEST_HELD", "ticket=" + (string)ticket + " labels=" + trackedLabels[idx]);
   }

   if(CloseOnRetestFailure && trackedHit21s[idx] && fav <= -RetestFailPoints)
   {
      long nowMs = GetTickMs();
      if(!trackedRetestFaileds[idx])
      {
         trackedRetestFaileds[idx] = true;
         trackedRetestFailStartMs[idx] = nowMs;
         trackedRetestFailStartFavs[idx] = fav;
         trackedRetestCollapseStartMs[idx] = 0;
         trackedRetestCollapseTicks[idx] = 0;
         trackedLabels[idx] += ";RETEST_FAIL_WARNING";
         LogInfo("RETEST_FAIL_WARNING", "ticket=" + (string)ticket +
                 " fav=" + DoubleToString(fav, 1) +
                 " close_min_loss=" + DoubleToString(RetestFailCloseMinLossPoints, 1) +
                 " labels=" + trackedLabels[idx]);
      }

      double collapseVelocity = RetestCollapseVelocity(idx, fav, nowMs);
      double collapseJump = trackedRetestFailStartFavs[idx] - fav;
      long warningAgeMs = nowMs - trackedRetestFailStartMs[idx];
      bool lossDeepEnough = (fav <= -RetestFailCloseMinLossPoints);
      bool folmAfterFollowRetestDanger = (FOLMAfterFollowRetestDangerClose &&
                                          TrackedLabelHas(idx, "SAR:FOLM") &&
                                          (trackedHit21s[idx] || trackedHit37s[idx]) &&
                                          FOLMAfterFollowRetestDangerLossPoints > 0.0 &&
                                          fav <= -FOLMAfterFollowRetestDangerLossPoints);
      bool retestPressure = (trackedMaes[idx] <= -OppositePressurePoints);
      bool v40RetestShieldVelocity = (V40RetestExecutionShieldMinVelocityPointsPerSec <= 0.0 ||
                                      collapseVelocity >= V40RetestExecutionShieldMinVelocityPointsPerSec);
      bool v40RetestShieldJump = (V40RetestExecutionShieldMinJumpPoints <= 0.0 ||
                                  collapseJump >= V40RetestExecutionShieldMinJumpPoints);
      bool v40RetestShield = (UseV40ExecutionShield &&
                              V40RetestExecutionShield &&
                              V40RetestExecutionShieldLossPoints > 0.0 &&
                              fav <= -V40RetestExecutionShieldLossPoints &&
                              warningAgeMs >= V40RetestExecutionShieldMinWarningAgeMs &&
                              (!V40RetestExecutionShieldNeedsPressure || retestPressure) &&
                              (v40RetestShieldVelocity || v40RetestShieldJump));
      if(v40RetestShield)
      {
         if(StringFind(trackedLabels[idx], "V40_RETEST_EXECUTION_SHIELD") < 0)
            trackedLabels[idx] += ";V40_RETEST_EXECUTION_SHIELD";
         if(retestPressure && StringFind(trackedLabels[idx], "OPPOSITE_PRESSURE") < 0)
            trackedLabels[idx] += ";OPPOSITE_PRESSURE";

         PrimeActiveCloseTelemetry(ticket, idx, fav, heldMs,
                                   "V40_RETEST_EXECUTION_SHIELD_CLOSE",
                                   V40RetestExecutionShieldLossPoints,
                                   "V40_RETEST_EXECUTION_SHIELD");
         if(ClosePositionWithComment(ticket, V40RetestExecutionShieldCloseComment, CONT_EXIT_LOSS, MathMax(RetestFailPoints,V40RetestExecutionShieldLossPoints)))
         {
            LogInfo("V40_RETEST_EXECUTION_SHIELD_CLOSE", "ticket=" + (string)ticket +
                    " fav=" + DoubleToString(fav, 1) +
                    " shield_loss=" + DoubleToString(V40RetestExecutionShieldLossPoints, 1) +
                    " velocity_pts_sec=" + DoubleToString(collapseVelocity, 1) +
                    " jump_pts=" + DoubleToString(collapseJump, 1) +
                    " warning_age_ms=" + (string)warningAgeMs +
                    " pressure=" + (retestPressure ? "true" : "false") +
                    " labels=" + trackedLabels[idx]);
            TrackerRemoveIndex(idx);
            return;
         }

         if(lastCloseRetcode == SAR_RETCODE_FROZEN)
         {
            MarkRetestStyleUrgentClose(ticket, fav, idx, "V40_RETEST_EXECUTION_SHIELD_URGENT",
                                       "V40_RETEST_EXECUTION_SHIELD_RETRY_ARMED",
                                       "shield_loss=" + DoubleToString(V40RetestExecutionShieldLossPoints, 1) +
                                       " velocity_pts_sec=" + DoubleToString(collapseVelocity, 1) +
                                       " jump_pts=" + DoubleToString(collapseJump, 1) +
                                       " warning_age_ms=" + (string)warningAgeMs +
                                       " pressure=" + (retestPressure ? "true" : "false"));
            return;
         }

         if(lastCloseRetcode == SAR_RETCODE_POSITION_CLOSED && !PositionSelectByTicket(ticket))
         {
            LogInfo("V40_RETEST_EXECUTION_SHIELD_POSITION_GONE", "ticket=" + (string)ticket +
                    " fav=" + DoubleToString(fav, 1) +
                    " shield_loss=" + DoubleToString(V40RetestExecutionShieldLossPoints, 1) +
                    " warning_age_ms=" + (string)warningAgeMs +
                    " retcode=" + (string)lastCloseRetcode +
                    " " + lastCloseRetcodeDescription +
                    " labels=" + trackedLabels[idx]);
            TrackerRemoveIndex(idx);
            return;
         }

         LogInfo("V40_RETEST_EXECUTION_SHIELD_CLOSE_FAILED", "ticket=" + (string)ticket +
                 " fav=" + DoubleToString(fav, 1) +
                 " shield_loss=" + DoubleToString(V40RetestExecutionShieldLossPoints, 1) +
                 " velocity_pts_sec=" + DoubleToString(collapseVelocity, 1) +
                 " jump_pts=" + DoubleToString(collapseJump, 1) +
                 " warning_age_ms=" + (string)warningAgeMs +
                 " retcode=" + (string)lastCloseRetcode +
                 " " + lastCloseRetcodeDescription +
                 " labels=" + trackedLabels[idx]);
         return;
      }
      if(folmAfterFollowRetestDanger && FOLMAfterFollowRetestBypassHold)
      {
         if(StringFind(trackedLabels[idx], "FOLM_AFTER_FOLLOW_RETEST_DANGER") < 0)
            trackedLabels[idx] += ";FOLM_AFTER_FOLLOW_RETEST_DANGER";
         if(ClosePositionWithComment(ticket, FOLMAfterFollowRetestDangerCloseComment, CONT_EXIT_LOSS, MathMax(RetestFailPoints,FOLMAfterFollowRetestDangerLossPoints)))
         {
            LogInfo("FOLM_AFTER_FOLLOW_RETEST_DANGER_CLOSE", "ticket=" + (string)ticket +
                    " fav=" + DoubleToString(fav, 1) +
                    " danger_loss=" + DoubleToString(FOLMAfterFollowRetestDangerLossPoints, 1) +
                    " warning_age_ms=" + (string)warningAgeMs +
                    " bypass_hold=" + (FOLMAfterFollowRetestBypassHold ? "true" : "false") +
                    " hit21=" + (trackedHit21s[idx] ? "true" : "false") +
                    " hit37=" + (trackedHit37s[idx] ? "true" : "false") +
                    " labels=" + trackedLabels[idx]);
            TrackerRemoveIndex(idx);
            return;
         }

         if(lastCloseRetcode == SAR_RETCODE_FROZEN)
         {
            MarkRetestCollapseUrgentClose(ticket, fav, idx, collapseVelocity, collapseJump,
                                          warningAgeMs, 0);
            return;
         }

         if(lastCloseRetcode == SAR_RETCODE_POSITION_CLOSED && !PositionSelectByTicket(ticket))
         {
            LogInfo("FOLM_AFTER_FOLLOW_RETEST_DANGER_POSITION_GONE", "ticket=" + (string)ticket +
                    " fav=" + DoubleToString(fav, 1) +
                    " danger_loss=" + DoubleToString(FOLMAfterFollowRetestDangerLossPoints, 1) +
                    " warning_age_ms=" + (string)warningAgeMs +
                    " retcode=" + (string)lastCloseRetcode +
                    " " + lastCloseRetcodeDescription +
                    " labels=" + trackedLabels[idx]);
            TrackerRemoveIndex(idx);
            return;
         }

         LogInfo("FOLM_AFTER_FOLLOW_RETEST_DANGER_CLOSE_FAILED", "ticket=" + (string)ticket +
                 " fav=" + DoubleToString(fav, 1) +
                 " danger_loss=" + DoubleToString(FOLMAfterFollowRetestDangerLossPoints, 1) +
                 " warning_age_ms=" + (string)warningAgeMs +
                 " retcode=" + (string)lastCloseRetcode +
                 " " + lastCloseRetcodeDescription +
                 " labels=" + trackedLabels[idx]);
      }
      bool collapseDeepEnough = (fav <= -RetestCollapseMinLossPoints);
      bool collapseVelocityFast = (collapseVelocity >= RetestCollapseVelocityPointsPerSec);
      bool collapseJumpFast = (RetestCollapseLookbackMs > 0 &&
                               warningAgeMs <= RetestCollapseLookbackMs &&
                               collapseJump >= RetestCollapseJumpPoints);
      bool collapseCandidate = (UseEmergencyRetestCollapseClose &&
                                collapseDeepEnough &&
                                (collapseVelocityFast || collapseJumpFast));

      if(collapseCandidate)
      {
         if(trackedRetestCollapseTicks[idx] <= 0)
         {
            trackedRetestCollapseStartMs[idx] = nowMs;
            trackedRetestCollapseTicks[idx] = 1;
            LogInfo("RETEST_COLLAPSE_ARMED", "ticket=" + (string)ticket +
                    " fav=" + DoubleToString(fav, 1) +
                    " velocity_pts_sec=" + DoubleToString(collapseVelocity, 1) +
                    " jump_pts=" + DoubleToString(collapseJump, 1) +
                    " warning_age_ms=" + (string)warningAgeMs +
                    " confirm_ticks=" + (string)RetestCollapseConfirmTicks +
                    " confirm_ms=" + (string)RetestCollapseConfirmMs +
                    " labels=" + trackedLabels[idx]);
         }
         else
            trackedRetestCollapseTicks[idx]++;

         long collapseConfirmMs = nowMs - trackedRetestCollapseStartMs[idx];
         bool collapseTicksConfirmed = (RetestCollapseConfirmTicks <= 1 ||
                                        trackedRetestCollapseTicks[idx] >= RetestCollapseConfirmTicks);
         bool collapseTimeConfirmed = (RetestCollapseConfirmMs <= 0 ||
                                       collapseConfirmMs >= RetestCollapseConfirmMs);

         if(collapseTicksConfirmed && collapseTimeConfirmed)
         {
            if(StringFind(trackedLabels[idx], "RETEST_COLLAPSE") < 0)
               trackedLabels[idx] += ";RETEST_COLLAPSE";
            if(ClosePositionWithComment(ticket, RetestCollapseCloseComment, CONT_EXIT_LOSS, MathMax(RetestFailPoints,RetestCollapseMinLossPoints)))
            {
               LogInfo("RETEST_COLLAPSE_CLOSE", "ticket=" + (string)ticket +
                       " fav=" + DoubleToString(fav, 1) +
                       " velocity_pts_sec=" + DoubleToString(collapseVelocity, 1) +
                       " jump_pts=" + DoubleToString(collapseJump, 1) +
                       " warning_age_ms=" + (string)warningAgeMs +
                       " confirm_ticks_seen=" + (string)trackedRetestCollapseTicks[idx] +
                       " confirm_ms_seen=" + (string)collapseConfirmMs +
                       " labels=" + trackedLabels[idx]);
               TrackerRemoveIndex(idx);
               return;
            }

            if(lastCloseRetcode == SAR_RETCODE_FROZEN)
            {
               MarkRetestCollapseUrgentClose(ticket, fav, idx, collapseVelocity, collapseJump,
                                             warningAgeMs, collapseConfirmMs);
               return;
            }

            if(lastCloseRetcode == SAR_RETCODE_POSITION_CLOSED && !PositionSelectByTicket(ticket))
            {
               LogInfo("RETEST_COLLAPSE_POSITION_GONE", "ticket=" + (string)ticket +
                       " fav=" + DoubleToString(fav, 1) +
                       " velocity_pts_sec=" + DoubleToString(collapseVelocity, 1) +
                       " jump_pts=" + DoubleToString(collapseJump, 1) +
                       " warning_age_ms=" + (string)warningAgeMs +
                       " confirm_ticks_seen=" + (string)trackedRetestCollapseTicks[idx] +
                       " confirm_ms_seen=" + (string)collapseConfirmMs +
                       " retcode=" + (string)lastCloseRetcode +
                       " " + lastCloseRetcodeDescription +
                       " labels=" + trackedLabels[idx]);
               TrackerRemoveIndex(idx);
               return;
            }

            LogInfo("RETEST_COLLAPSE_CLOSE_FAILED", "ticket=" + (string)ticket +
                    " fav=" + DoubleToString(fav, 1) +
                    " velocity_pts_sec=" + DoubleToString(collapseVelocity, 1) +
                    " jump_pts=" + DoubleToString(collapseJump, 1) +
                    " warning_age_ms=" + (string)warningAgeMs +
                    " confirm_ticks_seen=" + (string)trackedRetestCollapseTicks[idx] +
                    " confirm_ms_seen=" + (string)collapseConfirmMs +
                    " retcode=" + (string)lastCloseRetcode +
                    " " + lastCloseRetcodeDescription +
                    " labels=" + trackedLabels[idx]);
         }
      }
      else if(trackedRetestCollapseTicks[idx] > 0)
      {
         LogInfo("RETEST_COLLAPSE_DISARMED", "ticket=" + (string)ticket +
                 " fav=" + DoubleToString(fav, 1) +
                 " ticks_seen=" + (string)trackedRetestCollapseTicks[idx] +
                 " labels=" + trackedLabels[idx]);
         trackedRetestCollapseTicks[idx] = 0;
      }

      long collapseHoldAgeMs = 0;
      bool collapseHoldActive = false;
      if(RetestCollapseHoldNormalCloseMs > 0 && trackedRetestCollapseStartMs[idx] > 0)
      {
         collapseHoldAgeMs = nowMs - trackedRetestCollapseStartMs[idx];
         collapseHoldActive = (collapseHoldAgeMs < RetestCollapseHoldNormalCloseMs);
      }

      bool confirmOk = (RetestFailConfirmSeconds <= 0 ||
                        nowMs - trackedRetestFailStartMs[idx] >= RetestFailConfirmSeconds * 1000);
      bool hardFloorHit = (RetestCollapseHardMaxLossPoints > 0.0 &&
                           fav <= -RetestCollapseHardMaxLossPoints);
      if(confirmOk && hardFloorHit)
      {
         if(StringFind(trackedLabels[idx], "RETEST_HARD_FLOOR") < 0)
            trackedLabels[idx] += ";RETEST_HARD_FLOOR";
         if(ClosePositionWithComment(ticket, RetestCollapseHardCloseComment, CONT_EXIT_LOSS, MathMax(RetestFailPoints,RetestCollapseHardMaxLossPoints)))
         {
            LogInfo("RETEST_HARD_FLOOR_CLOSE", "ticket=" + (string)ticket +
                    " fav=" + DoubleToString(fav, 1) +
                    " hard_floor=" + DoubleToString(RetestCollapseHardMaxLossPoints, 1) +
                    " hold_active=" + (collapseHoldActive ? "true" : "false") +
                    " hold_age_ms=" + (string)collapseHoldAgeMs +
                    " labels=" + trackedLabels[idx]);
            TrackerRemoveIndex(idx);
            return;
         }

         if(lastCloseRetcode == SAR_RETCODE_FROZEN)
         {
            MarkHardFloorUrgentClose(ticket, fav, idx, collapseHoldActive, collapseHoldAgeMs);
            return;
         }

         if(ShouldLogHardFloorRetry(idx, nowMs))
         {
            LogInfo("RETEST_HARD_FLOOR_CLOSE_FAILED", "ticket=" + (string)ticket +
                    " fav=" + DoubleToString(fav, 1) +
                    " hard_floor=" + DoubleToString(RetestCollapseHardMaxLossPoints, 1) +
                    " hold_active=" + (collapseHoldActive ? "true" : "false") +
                    " hold_age_ms=" + (string)collapseHoldAgeMs +
                    " retcode=" + (string)lastCloseRetcode +
                    " " + lastCloseRetcodeDescription +
                    " labels=" + trackedLabels[idx]);
         }
         return;
      }
      bool earlyRetestCloseHit = (RetestFailedEarlyClose &&
                                  RetestFailedEarlyLossPoints > 0.0 &&
                                  fav <= -RetestFailedEarlyLossPoints &&
                                  (RetestFailedEarlyBypassHold || !collapseHoldActive));
      if(confirmOk && earlyRetestCloseHit)
      {
         if(StringFind(trackedLabels[idx], "RETEST_FAILED_EARLY") < 0)
            trackedLabels[idx] += ";RETEST_FAILED_EARLY";
         if(ClosePositionWithComment(ticket, RetestFailedEarlyCloseComment, CONT_EXIT_LOSS, MathMax(RetestFailPoints,RetestFailedEarlyLossPoints)))
         {
            LogInfo("RETEST_FAILED_EARLY_CLOSE", "ticket=" + (string)ticket +
                    " fav=" + DoubleToString(fav, 1) +
                    " early_loss=" + DoubleToString(RetestFailedEarlyLossPoints, 1) +
                    " hold_active=" + (collapseHoldActive ? "true" : "false") +
                    " bypass_hold=" + (RetestFailedEarlyBypassHold ? "true" : "false") +
                    " warning_age_ms=" + (string)warningAgeMs +
                    " labels=" + trackedLabels[idx]);
            TrackerRemoveIndex(idx);
            return;
         }

         if(lastCloseRetcode == SAR_RETCODE_FROZEN)
         {
            MarkRetestStyleUrgentClose(ticket, fav, idx, "RETEST_FAILED_EARLY_URGENT",
                                       "RETEST_FAILED_EARLY_RETRY_ARMED",
                                       "early_loss=" + DoubleToString(RetestFailedEarlyLossPoints, 1) +
                                       " hold_active=" + (collapseHoldActive ? "true" : "false") +
                                       " bypass_hold=" + (RetestFailedEarlyBypassHold ? "true" : "false") +
                                       " warning_age_ms=" + (string)warningAgeMs);
            return;
         }

         if(lastCloseRetcode == SAR_RETCODE_POSITION_CLOSED && !PositionSelectByTicket(ticket))
         {
            LogInfo("RETEST_FAILED_EARLY_POSITION_GONE", "ticket=" + (string)ticket +
                    " fav=" + DoubleToString(fav, 1) +
                    " early_loss=" + DoubleToString(RetestFailedEarlyLossPoints, 1) +
                    " retcode=" + (string)lastCloseRetcode +
                    " " + lastCloseRetcodeDescription +
                    " labels=" + trackedLabels[idx]);
            TrackerRemoveIndex(idx);
            return;
         }

         LogInfo("RETEST_FAILED_EARLY_CLOSE_FAILED", "ticket=" + (string)ticket +
                 " fav=" + DoubleToString(fav, 1) +
                 " early_loss=" + DoubleToString(RetestFailedEarlyLossPoints, 1) +
                 " retcode=" + (string)lastCloseRetcode +
                 " " + lastCloseRetcodeDescription +
                 " labels=" + trackedLabels[idx]);
         return;
      }
      if(confirmOk && lossDeepEnough && collapseHoldActive)
      {
         if(ShouldLogRetestPause(idx, nowMs))
         {
            LogInfo("RETEST_FAILED_CLOSE_PAUSED", "ticket=" + (string)ticket +
                    " fav=" + DoubleToString(fav, 1) +
                    " hold_age_ms=" + (string)collapseHoldAgeMs +
                    " hold_ms=" + (string)RetestCollapseHoldNormalCloseMs +
                    " labels=" + trackedLabels[idx]);
         }
      }
      if(confirmOk && lossDeepEnough && !collapseHoldActive)
      {
         trackedLabels[idx] += ";RETEST_FAILED";
         if(ClosePositionWithComment(ticket, RetestFailedCloseComment, CONT_EXIT_LOSS, MathMax(RetestFailPoints,RetestFailCloseMinLossPoints)))
         {
            LogInfo("RETEST_FAILED_CLOSE", "ticket=" + (string)ticket +
                    " fav=" + DoubleToString(fav, 1) +
                    " labels=" + trackedLabels[idx]);
            TrackerRemoveIndex(idx);
         }
         else
         {
            if(lastCloseRetcode == SAR_RETCODE_FROZEN)
            {
               MarkRetestStyleUrgentClose(ticket, fav, idx, "RETEST_FAILED_URGENT",
                                          "RETEST_FAILED_RETRY_ARMED",
                                          "close_min_loss=" + DoubleToString(RetestFailCloseMinLossPoints, 1) +
                                          " warning_age_ms=" + (string)warningAgeMs);
               return;
            }

            LogInfo("RETEST_FAILED_CLOSE_FAILED", "ticket=" + (string)ticket +
                    " fav=" + DoubleToString(fav, 1) +
                    " retcode=" + (string)lastCloseRetcode +
                    " " + lastCloseRetcodeDescription +
                    " labels=" + trackedLabels[idx]);
         }
      }
      return;
   }
   else if(trackedRetestFaileds[idx] && fav > -RetestFailPoints)
   {
      trackedRetestFaileds[idx] = false;
      trackedRetestFailStartMs[idx] = 0;
      trackedRetestFailStartFavs[idx] = 0.0;
      trackedRetestCollapseStartMs[idx] = 0;
      trackedRetestCollapseTicks[idx] = 0;
      trackedLabels[idx] += ";RETEST_RECOVERED";
      LogInfo("RETEST_RECOVERED", "ticket=" + (string)ticket +
              " fav=" + DoubleToString(fav, 1) +
              " labels=" + trackedLabels[idx]);
   }

   if(TryPreSpeedAgainstDefenseClose(ticket, fav, idx, heldMs))
      return;

   if(NoFollowEarlyClose)
   {
      bool earlyNoFollow = (!trackedHit21s[idx] && !trackedHit37s[idx]);
      bool earlyPressure = (trackedMaes[idx] <= -OppositePressurePoints);
      bool earlyTimeOk = (NoFollowEarlySeconds <= 0 ||
                          heldMs >= (long)NoFollowEarlySeconds * 1000);
      bool earlyLossOk = (NoFollowEarlyLossPoints > 0.0 &&
                          fav <= -NoFollowEarlyLossPoints);
      bool earlyPressureOk = (!NoFollowEarlyNeedsOppositePressure || earlyPressure);

      if(earlyNoFollow && earlyTimeOk && earlyLossOk && earlyPressureOk)
      {
         if(StringFind(trackedLabels[idx], "NO_FOLLOW_EARLY") < 0)
            trackedLabels[idx] += ";NO_FOLLOW_EARLY";
         if(earlyPressure && StringFind(trackedLabels[idx], "OPPOSITE_PRESSURE") < 0)
            trackedLabels[idx] += ";OPPOSITE_PRESSURE";

         if(ClosePositionWithComment(ticket, NoFollowEarlyCloseComment, CONT_EXIT_LOSS, NoFollowEarlyLossPoints))
         {
            LogInfo("NO_FOLLOW_EARLY_CLOSE", "ticket=" + (string)ticket +
                    " fav=" + DoubleToString(fav, 1) +
                    " held_ms=" + (string)heldMs +
                    " early_seconds=" + (string)NoFollowEarlySeconds +
                    " early_loss=" + DoubleToString(NoFollowEarlyLossPoints, 1) +
                    " pressure=" + (earlyPressure ? "true" : "false") +
                    " labels=" + trackedLabels[idx]);
            TrackerRemoveIndex(idx);
            return;
         }

         if(lastCloseRetcode == SAR_RETCODE_FROZEN)
         {
            MarkRetestStyleUrgentClose(ticket, fav, idx, "NO_FOLLOW_EARLY_URGENT",
                                       "NO_FOLLOW_EARLY_RETRY_ARMED",
                                       "held_ms=" + (string)heldMs +
                                       " early_seconds=" + (string)NoFollowEarlySeconds +
                                       " early_loss=" + DoubleToString(NoFollowEarlyLossPoints, 1) +
                                       " pressure=" + (earlyPressure ? "true" : "false"));
            return;
         }

         if(lastCloseRetcode == SAR_RETCODE_POSITION_CLOSED && !PositionSelectByTicket(ticket))
         {
            LogInfo("NO_FOLLOW_EARLY_POSITION_GONE", "ticket=" + (string)ticket +
                    " fav=" + DoubleToString(fav, 1) +
                    " held_ms=" + (string)heldMs +
                    " early_loss=" + DoubleToString(NoFollowEarlyLossPoints, 1) +
                    " retcode=" + (string)lastCloseRetcode +
                    " " + lastCloseRetcodeDescription +
                    " labels=" + trackedLabels[idx]);
            TrackerRemoveIndex(idx);
            return;
         }

         LogInfo("NO_FOLLOW_EARLY_CLOSE_FAILED", "ticket=" + (string)ticket +
                 " fav=" + DoubleToString(fav, 1) +
                 " held_ms=" + (string)heldMs +
                 " early_loss=" + DoubleToString(NoFollowEarlyLossPoints, 1) +
                 " retcode=" + (string)lastCloseRetcode +
                 " " + lastCloseRetcodeDescription +
                 " labels=" + trackedLabels[idx]);
         return;
      }
   }

   if(CloseIfNoFollowThrough && heldMs >= ValidationSeconds * 1000)
   {
      bool noFollow = (!trackedHit21s[idx] && !trackedHit37s[idx]);
      bool pressure = (trackedMaes[idx] <= -OppositePressurePoints);
      bool lossDeepEnough = (fav <= -NoFollowCloseMinLossPoints);
      if(noFollow && pressure && lossDeepEnough)
      {
         trackedLabels[idx] += ";OPPOSITE_PRESSURE";
         if(ClosePositionWithComment(ticket, NoFollowCloseComment, CONT_EXIT_LOSS, MathMax(0.0,NoFollowCloseMinLossPoints)))
         {
            LogInfo("NO_FOLLOW_CLOSE", "ticket=" + (string)ticket +
                    " fav=" + DoubleToString(fav, 1) +
                    " labels=" + trackedLabels[idx]);
            TrackerRemoveIndex(idx);
         }
         else
         {
            if(lastCloseRetcode == SAR_RETCODE_FROZEN)
            {
               MarkRetestStyleUrgentClose(ticket, fav, idx, "NO_FOLLOW_URGENT",
                                          "NO_FOLLOW_RETRY_ARMED",
                                          "held_ms=" + (string)heldMs +
                                          " close_min_loss=" + DoubleToString(NoFollowCloseMinLossPoints, 1) +
                                          " pressure=" + (pressure ? "true" : "false"));
               return;
            }

            LogInfo("NO_FOLLOW_CLOSE_FAILED", "ticket=" + (string)ticket +
                    " fav=" + DoubleToString(fav, 1) +
                    " retcode=" + (string)lastCloseRetcode +
                    " " + lastCloseRetcodeDescription +
                    " labels=" + trackedLabels[idx]);
         }
      }
   }
}

//+------------------------------------------------------------------+
long GetTickMs()
{
   MqlTick t;
   if(SymbolInfoTick(_Symbol, t))
      return t.time_msc;
   return (long)TimeCurrent() * 1000;
}

//+------------------------------------------------------------------+
// Gold pip convention: 1 pip = 0.10 in price, independent of quote digits.
// Other symbols retain the standard 3/5-digit fractional-pip convention.
double TrailingPipSizePrice()
{
   string baseCurrency = SymbolInfoString(_Symbol, SYMBOL_CURRENCY_BASE);
   if(baseCurrency == "XAU" || StringFind(_Symbol, "XAU") == 0 ||
      StringFind(_Symbol, "GOLD") == 0)
      return 0.10;
   return (_Digits == 3 || _Digits == 5 ? 10.0 * _Point : _Point);
}

//+------------------------------------------------------------------+
bool TrailingActivationProfitReached(const double favourablePoints)
{
   const double minimumProfitPips = 6.8;
   double minimumProfitPrice = minimumProfitPips * TrailingPipSizePrice();
   // Keep an exact 6.8-pip move below this strict "above" boundary despite
   // floating-point subtraction; this tolerance is far smaller than a tick.
   double boundaryTolerancePrice = _Point * 1e-6;
   return (favourablePoints * _Point >
           minimumProfitPrice + boundaryTolerancePrice);
}

//+------------------------------------------------------------------+
// Burst settling only grants permission to tighten a trailing SL.
// It never changes an entry, SL/TP geometry, or an explicit close rule.
bool ValidateBurstSettleInputs()
{
   if(!InpWaitForBurstSettle)
      return true;
   if(InpBurstSettleQuietMs < 100 || InpBurstSettleQuietMs > 60000 ||
      !MathIsValidNumber(InpBurstSettleSpeedFraction) ||
      InpBurstSettleSpeedFraction <= 0.0 || InpBurstSettleSpeedFraction > 1.0 ||
      !MathIsValidNumber(InpBurstSettleMaxSpeedPipsSec) ||
      InpBurstSettleMaxSpeedPipsSec <= 0.0 ||
      !MathIsValidNumber(InpBurstSettlePullbackPips) ||
      InpBurstSettlePullbackPips <= 0.0)
   {
      Print("BURST_SETTLE_INPUT_INVALID: quiet 100..60000 ms, speed fraction (0,1], positive finite speed cap and pullback required.");
      return false;
   }
   return true;
}

void BurstSettleReset(BurstSettleState &state, const long nowMs,
                      const double bid, const double ask)
{
   state.firstMs = nowMs;
   state.lastMs = nowMs;
   state.lastBid = bid;
   state.lastAsk = ask;
   state.bestMid = (bid + ask) * 0.5;
   state.bestBid = bid;
   state.bestAsk = ask;
   state.peakSpeed = 0.0;
   state.quietSinceMs = 0;
   state.allowed = false;
}

// Pure transition function; elapsed time comes only from real quote timestamps.
void BurstSettleStep(BurstSettleState &state, const long nowMs,
                     const double bid, const double ask,
                     const bool speedValid, const double speedPipsSec,
                     const double pipSize, const double speedFraction,
                     const double speedCap, const double pullbackPips,
                     const int quietMs)
{
   if(nowMs <= 0 || !MathIsValidNumber(bid) || !MathIsValidNumber(ask) ||
      bid <= 0.0 || ask < bid || pipSize <= 0.0)
   {
      state.firstMs = 0;
      state.quietSinceMs = 0;
      state.allowed = false;
      return;
   }
   if(state.firstMs <= 0 || nowMs < state.lastMs || nowMs - state.lastMs > 1000)
      BurstSettleReset(state, nowMs, bid, ask);

   state.lastMs = nowMs;
   state.lastBid = bid;
   state.lastAsk = ask;
   double mid = (bid + ask) * 0.5;
   double tolerance = pipSize * 1e-6;
   bool newExtreme = (state.side * (mid - state.bestMid) > tolerance);
   if(newExtreme)
   {
      // Keep Bid and Ask from the SAME favorable midpoint observation.
      state.bestMid = mid;
      state.bestBid = bid;
      state.bestAsk = ask;
   }
   bool valid = (speedValid && MathIsValidNumber(speedPipsSec) && speedPipsSec >= 0.0);
   if(valid)
      state.peakSpeed = MathMax(state.peakSpeed, speedPipsSec);
   double retrace = MathMin(state.side * (state.bestBid - bid),
                            state.side * (state.bestAsk - ask)) / pipSize;
   double maxQuietSpeed = MathMin(state.peakSpeed * speedFraction, speedCap);
   bool calm = (valid && !newExtreme && nowMs - state.firstMs >= 1000 &&
                state.peakSpeed > 0.0 &&
                speedPipsSec <= maxQuietSpeed + 1e-9 &&
                retrace + 1e-9 >= pullbackPips);
   if(!calm)
   {
      state.quietSinceMs = 0;
      state.allowed = false;
      return;
   }
   if(state.quietSinceMs == 0)
      state.quietSinceMs = nowMs;
   state.allowed = (nowMs - state.quietSinceMs >= quietMs);
}

// Sum absolute midpoint moves, so fast oscillation cannot masquerade as rest.
// The crossing boundary segment is included in full, conservatively overstating
// activity rather than inventing a tick price at the one-second boundary.
bool BurstSettleMeasureSpeed(const MqlTick &t, double &speedPipsSec)
{
   speedPipsSec = 0.0;
   int count = ArraySize(tickMs);
   double pipSize = TrailingPipSizePrice();
   if(count < 2 || ArraySize(tickMid) != count || ArraySize(tickSpread) != count ||
      t.time_msc <= 0 || pipSize <= 0.0)
      return false;
   int last = count - 1;
   double mid = (t.bid + t.ask) * 0.5;
   double spreadPrice = t.ask - t.bid;
   double tolerance = _Point * 1e-6;
   // OnTimer must not approve a quote missing from the tick history.
   if(tickMs[last] != t.time_msc ||
      MathAbs(tickMid[last] - mid) > tolerance ||
      MathAbs(tickSpread[last] * _Point - spreadPrice) > tolerance)
      return false;
   long startMs = t.time_msc - 1000;
   double distance = 0.0;
   int index = last;
   while(index > 0 && tickMs[index] > startMs)
   {
      long gap = tickMs[index] - tickMs[index - 1];
      if(gap < 0 || gap > 1000 ||
         !MathIsValidNumber(tickMid[index]) || !MathIsValidNumber(tickMid[index - 1]))
         return false;
      distance += MathAbs(tickMid[index] - tickMid[index - 1]);
      index--;
   }
   if(tickMs[index] > startMs)
      return false;
   speedPipsSec = distance / pipSize; // One-second observation window.
   return MathIsValidNumber(speedPipsSec);
}

int BurstSettleStateIndex(const long positionId, const int side,
                          const double entry, const MqlTick &t)
{
   for(int i = 0; i < ArraySize(burstSettleStates); i++)
   {
      if(burstSettleStates[i].positionId != positionId)
         continue;
      if(burstSettleStates[i].side != side ||
         MathAbs(burstSettleStates[i].entry - entry) > _Point * 1e-6)
      {
         burstSettleStates[i].side = side;
         burstSettleStates[i].entry = entry;
         BurstSettleReset(burstSettleStates[i], t.time_msc, t.bid, t.ask);
      }
      return i;
   }
   int index = ArraySize(burstSettleStates);
   ArrayResize(burstSettleStates, index + 1);
   burstSettleStates[index].positionId = positionId;
   burstSettleStates[index].side = side;
   burstSettleStates[index].entry = entry;
   BurstSettleReset(burstSettleStates[index], t.time_msc, t.bid, t.ask);
   return index;
}

void ObserveBurstSettlePosition(const ulong ticket, const int side,
                                const MqlTick &t)
{
   if(!InpWaitForBurstSettle || !PositionSelectByTicket(ticket))
      return;
   long positionId = PositionGetInteger(POSITION_IDENTIFIER);
   if(positionId <= 0)
      return;
   double entry = PositionGetDouble(POSITION_PRICE_OPEN);
   int index = BurstSettleStateIndex(positionId, side, entry, t);
   bool previouslyAllowed = burstSettleStates[index].allowed;
   double speed = 0.0;
   bool valid = BurstSettleMeasureSpeed(t, speed);
   BurstSettleStep(burstSettleStates[index], t.time_msc, t.bid, t.ask,
                  valid, speed, TrailingPipSizePrice(), InpBurstSettleSpeedFraction,
                  InpBurstSettleMaxSpeedPipsSec, InpBurstSettlePullbackPips,
                  InpBurstSettleQuietMs);
   if(previouslyAllowed != burstSettleStates[index].allowed)
   {
      double retrace = MathMin(side * (burstSettleStates[index].bestBid - t.bid),
                               side * (burstSettleStates[index].bestAsk - t.ask)) /
                               TrailingPipSizePrice();
      LogInfo(burstSettleStates[index].allowed ? "BURST_SETTLE_READY" : "BURST_SETTLE_WAIT",
              "ticket=" + (string)ticket +
              " speed_pips_sec=" + DoubleToString(speed, 2) +
              " peak_speed=" + DoubleToString(burstSettleStates[index].peakSpeed, 2) +
              " pullback_pips=" + DoubleToString(retrace, 2));
   }
}

bool BurstSettleAllowsTrailing(const ulong ticket, const int side, const MqlTick &t)
{
   if(!InpWaitForBurstSettle)
      return true;
   if(!PositionSelectByTicket(ticket))
      return false;
   long positionId = PositionGetInteger(POSITION_IDENTIFIER);
   double entry = PositionGetDouble(POSITION_PRICE_OPEN);
   for(int i = 0; i < ArraySize(burstSettleStates); i++)
   {
      if(burstSettleStates[i].positionId != positionId || burstSettleStates[i].side != side)
         continue;
      double tolerance = _Point * 1e-6;
      return (burstSettleStates[i].allowed &&
              MathAbs(burstSettleStates[i].entry - entry) <= tolerance &&
              burstSettleStates[i].lastMs == t.time_msc &&
              MathAbs(burstSettleStates[i].lastBid - t.bid) <= tolerance &&
              MathAbs(burstSettleStates[i].lastAsk - t.ask) <= tolerance);
   }
   return false;
}

void PruneBurstSettleStates()
{
   for(int i = ArraySize(burstSettleStates) - 1; i >= 0; i--)
   {
      bool exists = false;
      for(int p = 0; p < PositionsTotal(); p++)
      {
         if(PositionGetTicket(p) > 0 &&
            PositionGetInteger(POSITION_IDENTIFIER) == burstSettleStates[i].positionId)
         {
            exists = true;
            break;
         }
      }
      if(exists)
         continue;
      int count = ArraySize(burstSettleStates);
      for(int j = i + 1; j < count; j++)
         burstSettleStates[j - 1] = burstSettleStates[j];
      ArrayResize(burstSettleStates, count - 1);
   }
}


void TrailPosition(const ulong ticket, const int side, const double entry, const double oldSL, const double tp, const MqlTick &t)
{
   if(InpUseContinuationFreeze) return;
   double current = (side > 0 ? t.bid : t.ask);
   double fav = (side > 0 ? (current - entry) : (entry - current)) / _Point;
   if(!TrailingActivationProfitReached(fav) || fav < TrailStartPoints)
      return;

   double newSL = 0.0;
   double trailDistancePoints =
      ServerStopFloorPoints(TrailBehindPoints,
                            (side > 0 ? "BUY_TRAILING_SL" : "SELL_TRAILING_SL"),
                            ticket);
   if(side > 0)
   {
      newSL = NormalizeDouble(current - trailDistancePoints * _Point, _Digits);
      if(oldSL > 0.0 && newSL <= oldSL + TrailStepPoints * _Point)
         return;
   }
   else
   {
      newSL = NormalizeDouble(current + trailDistancePoints * _Point, _Digits);
      if(oldSL > 0.0 && newSL >= oldSL - TrailStepPoints * _Point)
         return;
   }

   if(!BurstSettleAllowsTrailing(ticket, side, t))
      return;

   if(trade.PositionModify(ticket, newSL, tp))
      LogInfo("TRAIL_MOVE", "ticket=" + (string)ticket + " fav=" + DoubleToString(fav, 1) +
              " sl=" + DoubleToString(newSL, _Digits));
}

//+------------------------------------------------------------------+
void TrailLayerWriteHeader()
{
   int h = FileOpen(SAR_TRAIL_LAYER_FILE,
                    FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI |
                    FILE_SHARE_READ | FILE_SHARE_WRITE, ",");
   if(h == INVALID_HANDLE)
   {
      if(!trailFileErrorLogged)
      {
         Print("SAR_TRAIL_LAYER_FILE_OPEN_FAILED error=", GetLastError());
         trailFileErrorLogged = true;
      }
      return;
   }
   if(FileSize(h) == 0)
      FileWrite(h, "schema_version", "row_kind", "time_msc", "symbol",
                "magic", "position_ticket", "position_id", "side",
                "trigger", "elapsed_ms", "favourable_pts",
                "live_spread_pts", "effective_spread_pts",
                "activation_pts_log_only", "inner_pts", "outer_pts",
                "applied_distance_pts", "peak_executable", "old_sl",
                "new_sl", "min_legal_pts", "modify_attempted", "status",
                "trade_retcode", "trade_retcode_description");
   FileClose(h);
}

//+------------------------------------------------------------------+
void CalculateTrailLayerGeometry(const double liveSpreadPoints,
                                 double &effectiveSpreadPoints,
                                 double &activationPoints,
                                 double &innerPoints,
                                 double &outerPoints,
                                 double &appliedDistancePoints)
{
   effectiveSpreadPoints = MathMax(liveSpreadPoints,
                                   InpReferenceSpreadPts);
   activationPoints = internalOrderDistance * effectiveSpreadPoints;
   outerPoints = MathMin(internalMaxTrailing * effectiveSpreadPoints,
                         InpTrailOuterCapPts);
   innerPoints = MathMin(internalMinTrailing * effectiveSpreadPoints,
                         outerPoints);
   appliedDistancePoints = MathMax(innerPoints,
                                   MathMin(outerPoints, activationPoints));
}

//+------------------------------------------------------------------+
int TrailLayerStateIndex(const ulong ticket)
{
   for(int i = 0; i < ArraySize(trailLayerStates); i++)
      if(trailLayerStates[i].ticket == ticket)
         return i;
   return -1;
}

//+------------------------------------------------------------------+
int EnsureTrailLayerState(const ulong ticket,
                          const int side,
                          const double entryPrice,
                          const double executablePrice,
                          const long nowMsc)
{
   int idx = TrailLayerStateIndex(ticket);
   if(idx >= 0)
      return idx;

   int n = ArraySize(trailLayerStates);
   ArrayResize(trailLayerStates, n + 1);
   trailLayerStates[n].ticket = ticket;
   trailLayerStates[n].positionId =
      (ulong)PositionGetInteger(POSITION_IDENTIFIER);
   trailLayerStates[n].fillTimeMsc =
      (long)PositionGetInteger(POSITION_TIME_MSC);
   if(trailLayerStates[n].fillTimeMsc <= 0)
      trailLayerStates[n].fillTimeMsc = nowMsc;
   trailLayerStates[n].side = side;
   trailLayerStates[n].entryPrice = entryPrice;
   trailLayerStates[n].peakExecutable = executablePrice;
   trailLayerStates[n].trailArmed = false;
   trailLayerStates[n].armTrigger = "";
   trailLayerStates[n].armTimeMsc = 0;
   trailLayerStates[n].lastTrailEvaluationMsc = 0;
   trailLayerStates[n].holdEvaluated = false;
   return n;
}

//+------------------------------------------------------------------+
void TrailLayerRemoveState(const int idx)
{
   int n = ArraySize(trailLayerStates);
   if(idx < 0 || idx >= n)
      return;
   for(int i = idx + 1; i < n; i++)
      trailLayerStates[i - 1] = trailLayerStates[i];
   ArrayResize(trailLayerStates, n - 1);
}

//+------------------------------------------------------------------+
void PruneTrailLayerStates()
{
   for(int i = ArraySize(trailLayerStates) - 1; i >= 0; i--)
      if(!PositionSelectByTicket(trailLayerStates[i].ticket))
         TrailLayerRemoveState(i);
}

//+------------------------------------------------------------------+
double QuantizeTrailLayerSL(const int side, const double price)
{
   double tickSize = sarTickSize;
   if(tickSize <= 0.0)
      tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0.0)
      return NormalizeDouble(price, _Digits);

   double ticks = price / tickSize;
   double quantized = (side > 0
                       ? MathFloor(ticks + 1e-9) * tickSize
                       : MathCeil(ticks - 1e-9) * tickSize);
   return NormalizeDouble(quantized, _Digits);
}

//+------------------------------------------------------------------+
void TrailLayerLogEvent(const TrailLayerPositionState &state,
                        const string rowKind,
                        const string trigger,
                        const long nowMsc,
                        const long elapsedMsc,
                        const double favourablePoints,
                        const double liveSpreadPoints,
                        const double effectiveSpreadPoints,
                        const double activationPoints,
                        const double innerPoints,
                        const double outerPoints,
                        const double appliedDistancePoints,
                        const double oldSL,
                        const double newSL,
                        const bool modifyAttempted,
                        const string status,
                        const uint retcode,
                        const string retcodeDescription)
{
   int h = FileOpen(SAR_TRAIL_LAYER_FILE,
                    FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI |
                    FILE_SHARE_READ | FILE_SHARE_WRITE, ",");
   if(h == INVALID_HANDLE)
   {
      if(!trailFileErrorLogged)
      {
         Print("SAR_TRAIL_LAYER_FILE_OPEN_FAILED error=", GetLastError());
         trailFileErrorLogged = true;
      }
      return;
   }

   FileSeek(h, 0, SEEK_END);
   FileWrite(h, "sar.traillayer.v1", rowKind, (string)nowMsc,
             _Symbol, (string)MagicNumber, (string)state.ticket,
             state.positionId > 0 ? (string)state.positionId : "UNAVAILABLE",
             state.side > 0 ? "BUY" : "SELL", trigger,
             (string)elapsedMsc, DoubleToString(favourablePoints, 3),
             DoubleToString(liveSpreadPoints, 3),
             DoubleToString(effectiveSpreadPoints, 3),
             DoubleToString(activationPoints, 3),
             DoubleToString(innerPoints, 3),
             DoubleToString(outerPoints, 3),
             DoubleToString(appliedDistancePoints, 3),
             DoubleToString(state.peakExecutable, _Digits),
             oldSL > 0.0 ? DoubleToString(oldSL, _Digits) : "UNAVAILABLE",
             newSL > 0.0 ? DoubleToString(newSL, _Digits) : "UNAVAILABLE",
             DoubleToString(sarMinLegalPts, 3), SarBool(modifyAttempted),
             status, retcode > 0 ? (string)retcode : "UNAVAILABLE",
             StringLen(retcodeDescription) > 0 ? retcodeDescription :
                                                "UNAVAILABLE");
   FileClose(h);
}

//+------------------------------------------------------------------+
bool ProcessPostFillHold(const ulong ticket,
                         const MqlTick &t,
                         const double favourablePoints,
                         TrailLayerPositionState &state)
{
   if(InpUseContinuationFreeze)
   {
      MqlTick continuationQuote;
      if(!SymbolInfoTick(_Symbol,continuationQuote)) return false;
      int continuationIndex=CFRObserve(ticket,continuationQuote);
      if(continuationIndex<0 || cfr_positions[continuationIndex].phase.frozen)
         return false; // Pause eligibility without consuming the one-time check.
   }
   if(!InpUse1000msHold || state.holdEvaluated)
      return false;

   long nowMsc = (t.time_msc > 0 ? t.time_msc : GetTickMs());
   long elapsedMsc = nowMsc - state.fillTimeMsc;
   if(elapsedMsc < 1000)
      return false;

   state.holdEvaluated = true;
   bool passed = (favourablePoints >= InpHoldMinFavPts);
   GateDecisionSnapshot snapshot;
   double mid = (t.bid + t.ask) * 0.5;
   CaptureGateDecisionSnapshot(state.side > 0 ? ActBuyMarket : ActSellMarket,
                               state.side, t, mid, snapshot);

   bool closeSent = false;
   uint closeRetcode = 0;
   string outcome = "HOLD_PASS";
   string savedVsForfeited = "NOT_VETOED";
   if(!passed)
   {
      savedVsForfeited = (favourablePoints < 0.0
                          ? "SAVED_LOSS_AT_TOUCH"
                          : "FORFEITED_GAIN_AT_TOUCH");
      closeSent = ClosePositionWithComment(ticket, "SAR_HOLD_KILL", CONT_EXIT_QUALITY, 0.0);
      closeRetcode = (closeSent ? TRADE_RETCODE_DONE : lastCloseRetcode);
      outcome = closeSent ? "HOLD_VETO_SENT" : "HOLD_VETO_REJECTED";
   }

   GateStackLogPostFillHold(snapshot, ticket, state.positionId,
                            elapsedMsc, favourablePoints, passed, outcome,
                            savedVsForfeited, closeSent, closeRetcode);
   return (!passed && closeSent);
}

//+------------------------------------------------------------------+
void ManageTrailLayer(const ulong ticket,
                      const int side,
                      const MqlTick &t,
                      TrailLayerPositionState &state)
{
   if(InpUseContinuationFreeze) return;
   if(!InpUseTrailLayer || !PositionSelectByTicket(ticket))
      return;

   long nowMsc = (t.time_msc > 0 ? t.time_msc : GetTickMs());
   double executable = (side > 0 ? t.bid : t.ask);
   if(side > 0)
      state.peakExecutable = MathMax(state.peakExecutable, executable);
   else
      state.peakExecutable = MathMin(state.peakExecutable, executable);

   double favourablePoints = (side > 0
                              ? executable - state.entryPrice
                              : state.entryPrice - executable) / _Point;
   long elapsedMsc = MathMax((long)0, nowMsc - state.fillTimeMsc);
   bool newlyArmed = false;
   if(!state.trailArmed)
   {
      // Time, cost and favourable-point triggers cannot bypass this floor.
      if(!TrailingActivationProfitReached(favourablePoints))
         return;

      if(InpArmOnCostDigested && favourablePoints >= sarCostDigestedPts)
         state.armTrigger = "COST_DIGESTED";
      else if(InpArmOnFavPts && favourablePoints >= InpTrailArmFavPts)
         state.armTrigger = "FAV";
      else if(InpArmOnTimeMs && elapsedMsc >= InpTrailArmTimeMs)
         state.armTrigger = "TIME";
      else
         return;

      state.trailArmed = true;
      state.armTimeMsc = nowMsc;
      newlyArmed = true;
   }
   else if(state.lastTrailEvaluationMsc > 0 &&
           nowMsc - state.lastTrailEvaluationMsc < InpModifyMinIntervalMs)
      return;

   state.lastTrailEvaluationMsc = nowMsc;
   double liveSpreadPoints = MathMax(0.0, (t.ask - t.bid) / _Point);
   double effectiveSpreadPoints = 0.0;
   double activationPoints = 0.0;
   double innerPoints = 0.0;
   double outerPoints = 0.0;
   double appliedDistancePoints = 0.0;
   CalculateTrailLayerGeometry(liveSpreadPoints, effectiveSpreadPoints,
                               activationPoints, innerPoints, outerPoints,
                               appliedDistancePoints);

   double oldSL = PositionGetDouble(POSITION_SL);
   double tp = PositionGetDouble(POSITION_TP);
   double rawSL = (side > 0
                   ? state.peakExecutable - appliedDistancePoints * _Point
                   : state.peakExecutable + appliedDistancePoints * _Point);
   double newSL = QuantizeTrailLayerSL(side, rawSL);
   bool improvement = (side > 0
                       ? (oldSL <= 0.0 || newSL > oldSL + sarTickSize * 0.5)
                       : (oldSL <= 0.0 || newSL < oldSL - sarTickSize * 0.5));
   string rowKind = newlyArmed ? "ARM" : "MODIFY";
   if(!improvement)
   {
      TrailLayerLogEvent(state, rowKind, state.armTrigger, nowMsc,
                         elapsedMsc, favourablePoints, liveSpreadPoints,
                         effectiveSpreadPoints, activationPoints, innerPoints,
                         outerPoints, appliedDistancePoints, oldSL, newSL,
                         false, "SKIPPED_NO_IMPROVEMENT", 0, "");
      return;
   }

   double legalDistancePoints = (side > 0
                                 ? t.bid - newSL
                                 : newSL - t.ask) / _Point;
   if(legalDistancePoints + 1e-9 < sarMinLegalPts)
   {
      TrailLayerLogEvent(state, rowKind, state.armTrigger, nowMsc,
                         elapsedMsc, favourablePoints, liveSpreadPoints,
                         effectiveSpreadPoints, activationPoints, innerPoints,
                         outerPoints, appliedDistancePoints, oldSL, newSL,
                         false, "SKIPPED_LEGALITY", 0, "");
      return;
   }

   if(!BurstSettleAllowsTrailing(ticket, side, t))
      return;

   ResetLastError();
   bool modifyCall = trade.PositionModify(ticket, newSL, tp);
   uint retcode = trade.ResultRetcode();
   bool sent = (modifyCall &&
                (retcode == TRADE_RETCODE_DONE ||
                 retcode == TRADE_RETCODE_PLACED));
   TrailLayerLogEvent(state, rowKind, state.armTrigger, nowMsc,
                      elapsedMsc, favourablePoints, liveSpreadPoints,
                      effectiveSpreadPoints, activationPoints, innerPoints,
                      outerPoints, appliedDistancePoints, oldSL, newSL,
                      true, sent ? "SENT" : "REJECTED", retcode,
                      trade.ResultRetcodeDescription());
}

//+------------------------------------------------------------------+
void WriteHeader()
{
   int h = FileOpen(CsvLogFileV483Cost, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      ClearTradeMeasurementContext();
      return;
   }
   if(FileSize(h) == 0)
   {
      string header = "";
      CsvAdd(header, "time");
      CsvAdd(header, "symbol");
      CsvAdd(header, "event");
      CsvAdd(header, "action");
      CsvAdd(header, "destination");
      CsvAdd(header, "scenario_key");
      CsvAdd(header, "scenario");
      CsvAdd(header, "labels");
      CsvAdd(header, "reason");
      CsvAdd(header, "buy_score");
      CsvAdd(header, "sell_score");
      CsvAdd(header, "speed_dir");
      CsvAdd(header, "speed_points");
      CsvAdd(header, "body_dir");
      CsvAdd(header, "body_pts");
      CsvAdd(header, "upper_wick");
      CsvAdd(header, "lower_wick");
      CsvAdd(header, "micro_dir");
      CsvAdd(header, "spread_stable");
      CsvAdd(header, "follow21");
      CsvAdd(header, "follow37");
      CsvAdd(header, "opposite_pressure");
      CsvAdd(header, "snapback");
      CsvAdd(header, "mfe");
      CsvAdd(header, "mae");
      CsvAdd(header, "retest_held");
      CsvAdd(header, "retest_failed");
      CsvAdd(header, "flow_fresh");
      CsvAdd(header, "flow_dir");
      CsvAdd(header, "force_imb");
      CsvAdd(header, "near_imb");
      CsvAdd(header, "book_imb");
      CsvAdd(header, "lots");
      CsvAdd(header, "entry");
      CsvAdd(header, "sl");
      CsvAdd(header, "tp");
      CsvAdd(header, "requested_price");
      CsvAdd(header, "executed_price");
      CsvAdd(header, "slippage_points");
      CsvAdd(header, "adverse_slippage_points");
      CsvAdd(header, "bid_at_request");
      CsvAdd(header, "ask_at_request");
      CsvAdd(header, "spread_at_request");
      CsvAdd(header, "velocity_1s");
      CsvAdd(header, "velocity_3s");
      CsvAdd(header, "velocity_5s");
      CsvAdd(header, "retcode");
      CsvAdd(header, "rule_true_ms");
      CsvAdd(header, "order_send_ms");
      CsvAdd(header, "fill_ms");
      CsvAdd(header, "rule_true_price");
      CsvAdd(header, "spread_at_rule_true");
      CsvAdd(header, "decision_drift_points");
      CsvAdd(header, "time_in_trade_seconds");
      CsvAdd(header, "mfe_before_close");
      CsvAdd(header, "mae_before_close");
      CsvAdd(header, "first_10s_mfe");
      CsvAdd(header, "freeze_level_points");
      CsvAdd(header, "warning_level_points");
      CsvAdd(header, "max_single_tick_adverse_pts");
      CsvAdd(header, "ticks_from_fill_to_warn24");
      CsvAdd(header, "ms_from_fill_to_warn15");
      CsvAdd(header, "ms_from_fill_to_warn18");
      CsvAdd(header, "ms_from_fill_to_warn21");
      CsvAdd(header, "ms_from_fill_to_warn24");
      CsvAdd(header, "fav_at_1s");
      CsvAdd(header, "fav_at_2s");
      CsvAdd(header, "fav_at_3s");
      CsvAdd(header, "quote_gap_ms");
      CsvAdd(header, "last_tick_delta_pts");
      CsvAdd(header, "tick_jump_direction");
      CsvAdd(header, "tick_jump_with_trade");
      CsvAdd(header, "tick_jump_against_trade");
      CsvAdd(header, "jump_followed_by_profit_1s");
      CsvAdd(header, "jump_followed_by_loss_1s");
      CsvAdd(header, "session_jump_quality");
      CsvAdd(header, "orderflow_agreed_during_jump");
      CsvAdd(header, "entry_tick_jump_with_trade");
      CsvAdd(header, "entry_tick_jump_against_trade");
      CsvAdd(header, "first_500ms_max_adverse_jump");
      CsvAdd(header, "first_1s_max_adverse_jump");
      CsvAdd(header, "first_2s_max_adverse_jump");
      CsvAdd(header, "pre_warn15_jump_against_trade");
      CsvAdd(header, "pre_warn18_jump_against_trade");
      CsvAdd(header, "pre_warn21_jump_against_trade");
      CsvAdd(header, "pre_warn24_jump_against_trade");
      CsvAdd(header, "closed_before_snapshot");
      CsvAdd(header, "v44_shadow_first1s_fired");
      CsvAdd(header, "v44_shadow_first1s_ms");
      CsvAdd(header, "v44_shadow_first1s_fav");
      CsvAdd(header, "v44_shadow_first1s_replay_delta");
      CsvAdd(header, "v44_shadow_first2s_fired");
      CsvAdd(header, "v44_shadow_first2s_ms");
      CsvAdd(header, "v44_shadow_first2s_fav");
      CsvAdd(header, "v44_shadow_first2s_replay_delta");
      CsvAdd(header, "v44_folm_sm_ghost_started");
      CsvAdd(header, "v451_lowj_first1s_fired");
      CsvAdd(header, "v451_lowj_first1s_ms");
      CsvAdd(header, "v451_lowj_first1s_fav");
      CsvAdd(header, "v451_lowj_first1s_replay_delta");
      CsvAdd(header, "v451_lowj_first1s_lead_ms");
      CsvAdd(header, "v451_lowj_first1s_before_current_shield");
      CsvAdd(header, "v451_lowj_first2s_fired");
      CsvAdd(header, "v451_lowj_first2s_ms");
      CsvAdd(header, "v451_lowj_first2s_fav");
      CsvAdd(header, "v451_lowj_first2s_replay_delta");
      CsvAdd(header, "v451_lowj_first2s_lead_ms");
      CsvAdd(header, "v451_lowj_first2s_before_current_shield");
      CsvAdd(header, "v451_actual_close_event");
      CsvAdd(header, "v451_actual_close_fav");
      CsvAdd(header, "v451_actual_close_held_ms");
      CsvAdd(header, "v451_flow_opp_audit_flag");
      CsvAdd(header, "v451_flow_opp_source_timing");
      CsvAdd(header, "v451_flow_opp_source_ms");
      CsvAdd(header, "v451_flow_opp_source_fav");
      CsvAdd(header, "folm_quality_shadow_score");
      CsvAdd(header, "folm_quality_bucket");
      CsvAdd(header, "folm_low_quality_would_block");
      CsvAdd(header, "folm_low_quality_replay_delta");
      CsvAdd(header, "folm_fav_2s_bucket");
      CsvAdd(header, "folm_fav_3s_bucket");
      CsvAdd(header, "folm_first10s_mfe_bucket");
      CsvAdd(header, "pre_entry_high_shadow_score");
      CsvAdd(header, "pre_entry_high_shadow_bucket");
      CsvAdd(header, "pre_entry_high_would_allow");
      CsvAdd(header, "pre_entry_high_would_block");
      CsvAdd(header, "pre_entry_high_shadow_signals");
      CsvAdd(header, "v452_low_microscope_active");
      CsvAdd(header, "v452_low_final_path");
      CsvAdd(header, "v452_low_entry_route");
      CsvAdd(header, "v452_low_recovery_profile");
      CsvAdd(header, "v452_low_fav1_to_fav3_delta");
      CsvAdd(header, "v452_low_fav2_to_fav3_delta");
      CsvAdd(header, "v452_low_max_fav_1to3");
      CsvAdd(header, "v452_low_had_1s_adverse_jump");
      CsvAdd(header, "v452_low_had_2s_adverse_jump");
      CsvAdd(header, "v452_low_jump_recovered_by_3s");
      CsvAdd(header, "v452_low_jump_recovered_to_speed");
      CsvAdd(header, "v452_low_pressure_actionable");
      CsvAdd(header, "v452_low_pressure_before_3s");
      CsvAdd(header, "v452_low_escape_reason");
      CsvAdd(header, "v452_low_kill_risk_flag");
      CsvAdd(header, "v452_low_dead_strict");
      CsvAdd(header, "v46_low_dead_shadow_fired");
      CsvAdd(header, "v46_low_dead_shadow_ms");
      CsvAdd(header, "v46_low_dead_shadow_fav");
      CsvAdd(header, "v46_low_dead_shadow_mfe");
      CsvAdd(header, "v46_low_dead_shadow_max_fav_1to3");
      CsvAdd(header, "v46_low_dead_shadow_replay_delta");
      CsvAdd(header, "v46_low_dead_shadow_lead_ms");
      CsvAdd(header, "v46_low_dead_shadow_before_current_shield");
      CsvAdd(header, "v46_low_dead_shadow_final_path");
      CsvAdd(header, "v46_low_dead_shadow_speed_touched");
      CsvAdd(header, "v46_low_dead_shadow_reason");
      CsvAdd(header, "v461_fav_at_250ms");
      CsvAdd(header, "v461_fav_at_500ms");
      CsvAdd(header, "v461_time_to_first_profit_ms");
      CsvAdd(header, "v461_time_to_mfe_10_ms");
      CsvAdd(header, "v461_time_to_mfe_20_ms");
      CsvAdd(header, "v461_time_to_mfe_40_ms");
      CsvAdd(header, "v461_mfe_slope_1s_to_3s");
      CsvAdd(header, "v461_max_pullback_after_first_profit");
      CsvAdd(header, "v461_high_mid_micro_class");
      CsvAdd(header, "v461_high_mid_time_to_speed_ms");
      CsvAdd(header, "v461_high_mid_failed_reason");
      CsvAdd(header, "v461_low_detect_ms");
      CsvAdd(header, "v461_low_detect_fav");
      CsvAdd(header, "v461_low_detect_spread");
      CsvAdd(header, "v461_low_detect_orderflow_state");
      CsvAdd(header, "v461_low_detect_pressure_state");
      CsvAdd(header, "v461_opposite_at_entry_shadow_mfe");
      CsvAdd(header, "v461_opposite_at_entry_shadow_mae");
      CsvAdd(header, "v461_opposite_at_entry_would_speed");
      CsvAdd(header, "v461_opposite_at_entry_net_delta");
      CsvAdd(header, "v461_opposite_at_low_shadow_mfe");
      CsvAdd(header, "v461_opposite_at_low_shadow_mae");
      CsvAdd(header, "v461_opposite_at_low_would_speed");
      CsvAdd(header, "v461_opposite_at_low_would_hard_lose");
      CsvAdd(header, "v461_opposite_at_low_net_delta");
      CsvAdd(header, "v461_low_micro_class");
      CsvAdd(header, "v461_low_micro_class_reason");
      CsvAdd(header, "v47_bucket_present");
      CsvAdd(header, "v47_bucket_null_reason");
      CsvAdd(header, "v47_bucket_audit_close_reason");
      CsvAdd(header, "v47_bucket_audit_route");
      CsvAdd(header, "v47_bucket_audit_session");
      CsvAdd(header, "v47_bucket_audit_spread");
      CsvAdd(header, "v47_bucket_audit_final_path");
      CsvAdd(header, "v47_entry_avoid_shadow");
      CsvAdd(header, "v47_500ms_avoid_shadow");
      CsvAdd(header, "v47_1s_avoid_shadow");
      CsvAdd(header, "v47_2s_avoid_shadow");
      CsvAdd(header, "v47_3s_avoid_shadow");
      CsvAdd(header, "v47_first_avoid_time_ms");
      CsvAdd(header, "v47_first_avoid_stage");
      CsvAdd(header, "v47_avoid_reason");
      CsvAdd(header, "v47_avoid_replay_delta");
      CsvAdd(header, "v47_would_block_low_no_trade");
      CsvAdd(header, "v47_would_block_low_unresolved");
      CsvAdd(header, "v47_would_block_high");
      CsvAdd(header, "v47_would_block_mid");
      CsvAdd(header, "v47_would_block_speed");
      CsvAdd(header, "v47_pre_entry_shadow_score");
      CsvAdd(header, "v47_pre_entry_shadow_bucket");
      CsvAdd(header, "v47_pre_entry_shadow_signals");
      CsvAdd(header, "v47_time_to_first_favorable_tick_ms");
      CsvAdd(header, "v47_first_500ms_adverse_jump");
      CsvAdd(header, "v47_first_1s_adverse_jump");
      CsvAdd(header, "v47_first_2s_adverse_jump");
      CsvAdd(header, "v47_frontier_notes");
      CsvAdd(header, "v471_schema_version");
      CsvAdd(header, "v471_route_scope");
      CsvAdd(header, "v471_alive_100ms");
      CsvAdd(header, "v471_alive_250ms");
      CsvAdd(header, "v471_alive_500ms");
      CsvAdd(header, "v471_alive_750ms");
      CsvAdd(header, "v471_alive_1s");
      CsvAdd(header, "v471_alive_1500ms");
      CsvAdd(header, "v471_alive_2s");
      CsvAdd(header, "v471_alive_3s");
      CsvAdd(header, "v471_sample_ms_100ms");
      CsvAdd(header, "v471_sample_ms_250ms");
      CsvAdd(header, "v471_sample_ms_500ms");
      CsvAdd(header, "v471_sample_ms_750ms");
      CsvAdd(header, "v471_sample_ms_1s");
      CsvAdd(header, "v471_sample_ms_1500ms");
      CsvAdd(header, "v471_sample_ms_2s");
      CsvAdd(header, "v471_sample_ms_3s");
      CsvAdd(header, "v471_fav_100ms");
      CsvAdd(header, "v471_fav_250ms");
      CsvAdd(header, "v471_fav_500ms");
      CsvAdd(header, "v471_fav_750ms");
      CsvAdd(header, "v471_fav_1s");
      CsvAdd(header, "v471_fav_1500ms");
      CsvAdd(header, "v471_fav_2s");
      CsvAdd(header, "v471_fav_3s");
      CsvAdd(header, "v471_ticks_100ms");
      CsvAdd(header, "v471_ticks_250ms");
      CsvAdd(header, "v471_ticks_500ms");
      CsvAdd(header, "v471_ticks_750ms");
      CsvAdd(header, "v471_ticks_1s");
      CsvAdd(header, "v471_ticks_1500ms");
      CsvAdd(header, "v471_ticks_2s");
      CsvAdd(header, "v471_ticks_3s");
      CsvAdd(header, "v471_first_250ms_adverse_jump");
      CsvAdd(header, "v471_first_500ms_adverse_jump");
      CsvAdd(header, "v471_first_750ms_adverse_jump");
      CsvAdd(header, "v471_first_1s_adverse_jump");
      CsvAdd(header, "v471_first_2s_adverse_jump");
      CsvAdd(header, "v471_tick_path_1to8");
      CsvAdd(header, "v471_pre_entry_tape_health");
      CsvAdd(header, "v471_pre_entry_velocity_decay");
      CsvAdd(header, "v471_pre_speed_signal_age_ms");
      CsvAdd(header, "v471_first_favorable_tick_state");
      CsvAdd(header, "v471_entry_avoid_shadow");
      CsvAdd(header, "v471_250ms_avoid_shadow");
      CsvAdd(header, "v471_500ms_avoid_shadow");
      CsvAdd(header, "v471_750ms_avoid_shadow");
      CsvAdd(header, "v471_1s_avoid_shadow");
      CsvAdd(header, "v471_first_avoid_time_ms");
      CsvAdd(header, "v471_first_avoid_stage");
      CsvAdd(header, "v471_avoid_reason");
      CsvAdd(header, "v471_avoid_replay_delta");
      CsvAdd(header, "v471_would_block_low_no_trade");
      CsvAdd(header, "v471_would_block_low_unresolved");
      CsvAdd(header, "v471_would_block_high");
      CsvAdd(header, "v471_would_block_mid");
      CsvAdd(header, "v471_would_block_speed");
      CsvAdd(header, "v471_coverage_note");
      CsvAdd(header, "v48_mode2_shadow_signal");
      CsvAdd(header, "v48_mode2_would_allow");
      CsvAdd(header, "v48_mode2_would_block");
      CsvAdd(header, "v48_mode2_block_reason");
      CsvAdd(header, "v48_mode2_opp_flags");
      CsvAdd(header, "v48_mode2_velocity_1s");
      CsvAdd(header, "v48_mode2_weight_factor");
      CsvAdd(header, "retry_count");
      CsvAdd(header, "ms_in_frozen_state");
      CsvAdd(header, "session_bucket");
      CsvAdd(header, "spread_regime");
      CsvAdd(header, "deal_position_identifier");
      CsvAdd(header, "deal_profit_money");
      CsvAdd(header, "deal_commission_money");
      CsvAdd(header, "deal_swap_money");
      CsvAdd(header, "deal_fee_money");
      CsvAdd(header, "deal_net_money");
      CsvAdd(header, "deal_costs_complete");
      CsvAdd(header, "deal_ledger_deals");
      CsvAdd(header, "position_ticket");
      CsvAdd(header, "magic_number");
      CsvAdd(header, "symbol");
      CsvAdd(header, "close_mechanism");
      CsvAdd(header, "close_price");
      CsvAdd(header, "close_server_time_msc");
      CsvAdd(header, "closing_deal_ticket");
      CsvAdd(header, "run_tag");
      CsvWriteLine(h, header);
   }
   FileClose(h);
}

//+------------------------------------------------------------------+
void LogDecision(const string eventName, const RouterAction action, const DirectionState &s, const string reason,
                 const double lots, const double entry, const double sl, const double tp)
{
   DirectionState captureLogState=s;
   if(StringFind(eventName,"SKIP")==0 && captureLogState.capture.decision_gate_verdict=="NOT_EVALUATED")
      SARCaptureDecisionGate(captureLogState.capture,"BLOCKED",reason);
   SarOrderFlowDecisionLog(eventName, action, captureLogState);

   int h = FileOpen(CsvLogFileV483Cost, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      ClearTradeMeasurementContext();
      return;
   }
   FileSeek(h, 0, SEEK_END);
   string scenarioKey = ScenarioKeyForAction(action, s);
   int jumpTelemetrySide = (logRuleTelemetryActive && logRuleSide != 0 ? logRuleSide : ActionSide(action));
   BuildV42JumpDirectionTelemetry(logRuleTelemetryActive, jumpTelemetrySide, logLastTickDeltaPts, logFavAt1s, s,
                                  logTickJumpDirection, logTickJumpWithTrade, logTickJumpAgainstTrade,
                                  logJumpFollowedByProfit1s, logJumpFollowedByLoss1s,
                                  logSessionJumpQuality, logOrderFlowAgreedDuringJump);
   string row = "";
   CsvAdd(row, TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS));
   CsvAdd(row, _Symbol);
   CsvAdd(row, eventName);
   CsvAdd(row, ActionName(action));
   CsvAdd(row, ActionDestination(action));
   CsvAdd(row, scenarioKey);
   CsvAdd(row, s.scenario);
   CsvAdd(row, s.labels);
   CsvAdd(row, reason);
   CsvAdd(row, DoubleToString(s.buyScore, 2));
   CsvAdd(row, DoubleToString(s.sellScore, 2));
   CsvAdd(row, (string)speedDir);
   CsvAdd(row, DoubleToString(speedPoints, 1));
   CsvAdd(row, (string)s.bodyDir);
   CsvAdd(row, DoubleToString(s.bodyPts, 1));
   CsvAdd(row, DoubleToString(s.upperWickPts, 1));
   CsvAdd(row, DoubleToString(s.lowerWickPts, 1));
   CsvAdd(row, (string)s.microDir);
   CsvAdd(row, (s.spreadStable ? "true" : "false"));
   CsvAdd(row, (s.follow21 ? "true" : "false"));
   CsvAdd(row, (s.follow37 ? "true" : "false"));
   CsvAdd(row, (s.oppositePressure ? "true" : "false"));
   CsvAdd(row, (s.snapback ? "true" : "false"));
   CsvAdd(row, DoubleToString(s.mfe, 1));
   CsvAdd(row, DoubleToString(s.mae, 1));
   CsvAdd(row, (s.retestHeld ? "true" : "false"));
   CsvAdd(row, (s.retestFailed ? "true" : "false"));
   CsvAdd(row, (s.flowFresh ? "true" : "false"));
   CsvAdd(row, (string)s.flowDir);
   CsvAdd(row, DoubleToString(s.forceImb, 1));
   CsvAdd(row, DoubleToString(s.nearImb, 1));
   CsvAdd(row, DoubleToString(s.bookImb, 1));
   CsvAdd(row, DoubleToString(lots, 2));
   CsvAdd(row, DoubleToString(entry, _Digits));
   CsvAdd(row, DoubleToString(sl, _Digits));
   CsvAdd(row, DoubleToString(tp, _Digits));
   CsvAdd(row, MeasurementDouble(logTradeMeasurementActive, logRequestedPrice, _Digits));
   CsvAdd(row, MeasurementDouble(logTradeMeasurementActive, logExecutedPrice, _Digits));
   CsvAdd(row, MeasurementDouble(logTradeMeasurementActive, logSlippagePoints, 1));
   CsvAdd(row, MeasurementDouble(logTradeMeasurementActive, logAdverseSlippagePoints, 1));
   CsvAdd(row, MeasurementDouble(logTradeMeasurementActive, logBidAtRequest, _Digits));
   CsvAdd(row, MeasurementDouble(logTradeMeasurementActive, logAskAtRequest, _Digits));
   CsvAdd(row, MeasurementDouble(logTradeMeasurementActive, logSpreadAtRequest, 1));
   CsvAdd(row, MeasurementDouble(logTradeMeasurementActive, logVelocity1s, 1));
   CsvAdd(row, MeasurementDouble(logTradeMeasurementActive, logVelocity3s, 1));
   CsvAdd(row, MeasurementDouble(logTradeMeasurementActive, logVelocity5s, 1));
   CsvAdd(row, (logTradeMeasurementActive ? (string)logTradeRetcode : ""));
   CsvAdd(row, MeasurementLong(logRuleTelemetryActive, logRuleTrueMs));
   CsvAdd(row, MeasurementLong(logRuleTelemetryActive, logOrderSendMs));
   CsvAdd(row, MeasurementLong(logRuleTelemetryActive, logFillMs));
   CsvAdd(row, MeasurementDouble(logRuleTelemetryActive, logRuleTruePrice, _Digits));
   CsvAdd(row, MeasurementDouble(logRuleTelemetryActive, logSpreadAtRuleTrue, 1));
   CsvAdd(row, MeasurementDouble(logRuleTelemetryActive, logDecisionDriftPoints, 1));
   CsvAdd(row, MeasurementDouble(logRuleTelemetryActive, logTimeInTradeSeconds, 2));
   CsvAdd(row, MeasurementDouble(logRuleTelemetryActive, logMfeBeforeClose, 1));
   CsvAdd(row, MeasurementDouble(logRuleTelemetryActive, logMaeBeforeClose, 1));
   CsvAdd(row, MeasurementDouble(logRuleTelemetryActive, logFirst10sMfe, 1));
   CsvAdd(row, MeasurementDouble(logRuleTelemetryActive, logFreezeLevelPoints, 1));
   CsvAdd(row, MeasurementDouble(logRuleTelemetryActive, logWarningLevelPoints, 1));
   CsvAdd(row, MeasurementDouble(logRuleTelemetryActive, logMaxSingleTickAdversePts, 1));
   CsvAdd(row, (logRuleTelemetryActive && logTicksFromFillToWarn24 > 0 ? (string)logTicksFromFillToWarn24 : ""));
   CsvAdd(row, MeasurementLong(logRuleTelemetryActive, logMsFromFillToWarn15));
   CsvAdd(row, MeasurementLong(logRuleTelemetryActive, logMsFromFillToWarn18));
   CsvAdd(row, MeasurementLong(logRuleTelemetryActive, logMsFromFillToWarn21));
   CsvAdd(row, MeasurementLong(logRuleTelemetryActive, logMsFromFillToWarn24));
   CsvAdd(row, MeasurementDoubleSentinel(logRuleTelemetryActive, logFavAt1s, 1));
   CsvAdd(row, MeasurementDoubleSentinel(logRuleTelemetryActive, logFavAt2s, 1));
   CsvAdd(row, MeasurementDoubleSentinel(logRuleTelemetryActive, logFavAt3s, 1));
   CsvAdd(row, MeasurementLong(logRuleTelemetryActive, logQuoteGapMs));
   CsvAdd(row, MeasurementDouble(logRuleTelemetryActive, logLastTickDeltaPts, 1));
   CsvAdd(row, (logRuleTelemetryActive ? logTickJumpDirection : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logTickJumpWithTrade : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logTickJumpAgainstTrade : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logJumpFollowedByProfit1s : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logJumpFollowedByLoss1s : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logSessionJumpQuality : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logOrderFlowAgreedDuringJump : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logEntryTickJumpWithTrade : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logEntryTickJumpAgainstTrade : ""));
   CsvAdd(row, MeasurementDouble(logRuleTelemetryActive, logFirst500msMaxAdverseJumpPts, 1));
   CsvAdd(row, MeasurementDouble(logRuleTelemetryActive, logFirst1sMaxAdverseJumpPts, 1));
   CsvAdd(row, MeasurementDouble(logRuleTelemetryActive, logFirst2sMaxAdverseJumpPts, 1));
   CsvAdd(row, (logRuleTelemetryActive ? logPreWarn15JumpAgainstTrade : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logPreWarn18JumpAgainstTrade : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logPreWarn21JumpAgainstTrade : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logPreWarn24JumpAgainstTrade : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logClosedBeforeSnapshot : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV44ShadowFirst1sFired : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV44ShadowFirst1sFired == "true" ? (string)logV44ShadowFirst1sMs : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV44ShadowFirst1sFired == "true" ? DoubleToString(logV44ShadowFirst1sFav, 1) : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV44ShadowFirst1sFired == "true" ? DoubleToString(logV44ShadowFirst1sReplayDelta, 1) : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV44ShadowFirst2sFired : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV44ShadowFirst2sFired == "true" ? (string)logV44ShadowFirst2sMs : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV44ShadowFirst2sFired == "true" ? DoubleToString(logV44ShadowFirst2sFav, 1) : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV44ShadowFirst2sFired == "true" ? DoubleToString(logV44ShadowFirst2sReplayDelta, 1) : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV44FOLMSGhostStarted : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV451LowJFirst1sFired : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV451LowJFirst1sFired == "true" ? (string)logV451LowJFirst1sMs : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV451LowJFirst1sFired == "true" ? DoubleToString(logV451LowJFirst1sFav, 1) : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV451LowJFirst1sFired == "true" ? DoubleToString(logV451LowJFirst1sReplayDelta, 1) : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV451LowJFirst1sFired == "true" ? (string)logV451LowJFirst1sLeadMs : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV451LowJFirst1sBeforeCurrentShield : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV451LowJFirst2sFired : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV451LowJFirst2sFired == "true" ? (string)logV451LowJFirst2sMs : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV451LowJFirst2sFired == "true" ? DoubleToString(logV451LowJFirst2sFav, 1) : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV451LowJFirst2sFired == "true" ? DoubleToString(logV451LowJFirst2sReplayDelta, 1) : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV451LowJFirst2sFired == "true" ? (string)logV451LowJFirst2sLeadMs : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV451LowJFirst2sBeforeCurrentShield : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV451ActualCloseEvent : ""));
   CsvAdd(row, (logRuleTelemetryActive ? DoubleToString(logV451ActualCloseFav, 1) : ""));
   CsvAdd(row, (logRuleTelemetryActive ? (string)logV451ActualCloseHeldMs : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV451FlowOppAuditFlag : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV451FlowOppSourceTiming : ""));
   CsvAdd(row, (logRuleTelemetryActive && StringLen(logV451FlowOppSourceTiming) > 0 ? (string)logV451FlowOppSourceMs : ""));
   CsvAdd(row, (logRuleTelemetryActive && StringLen(logV451FlowOppSourceTiming) > 0 ? DoubleToString(logV451FlowOppSourceFav, 1) : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV45FOLMQualityScore : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV45FOLMQualityBucket : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV45FOLMLowQualityWouldBlock : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV45FOLMLowQualityReplayDelta : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV45FOLMFav2sBucket : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV45FOLMFav3sBucket : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV45FOLMFirst10sMfeBucket : ""));
   CsvAdd(row, logV45PreEntryHighShadowScore);
   CsvAdd(row, logV45PreEntryHighShadowBucket);
   CsvAdd(row, logV45PreEntryHighWouldAllow);
   CsvAdd(row, logV45PreEntryHighWouldBlock);
   CsvAdd(row, logV45PreEntryHighSignals);
   CsvAdd(row, (logRuleTelemetryActive ? logV452LowMicroscopeActive : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV452LowFinalPath : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV452LowEntryRoute : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV452LowRecoveryProfile : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV452LowFav1ToFav3Delta : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV452LowFav2ToFav3Delta : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV452LowMaxFav1To3 : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV452LowHad1sAdverseJump : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV452LowHad2sAdverseJump : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV452LowJumpRecoveredBy3s : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV452LowJumpRecoveredToSpeed : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV452LowPressureActionable : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV452LowPressureBefore3s : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV452LowEscapeReason : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV452LowKillRiskFlag : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV452LowDeadStrict : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV46LowDeadShadowFired : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV46LowDeadShadowFired == "true" ? (string)logV46LowDeadShadowMs : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV46LowDeadShadowFired == "true" ? DoubleToString(logV46LowDeadShadowFav, 1) : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV46LowDeadShadowFired == "true" ? DoubleToString(logV46LowDeadShadowMfe, 1) : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV46LowDeadShadowFired == "true" ? DoubleToString(logV46LowDeadShadowMaxFav1To3, 1) : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV46LowDeadShadowFired == "true" ? DoubleToString(logV46LowDeadShadowReplayDelta, 1) : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV46LowDeadShadowFired == "true" ? (string)logV46LowDeadShadowLeadMs : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV46LowDeadShadowBeforeCurrentShield : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV46LowDeadShadowFired == "true" ? logV46LowDeadShadowFinalPath : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV46LowDeadShadowFired == "true" ? logV46LowDeadShadowSpeedTouched : ""));
   CsvAdd(row, (logRuleTelemetryActive && logV46LowDeadShadowFired == "true" ? logV46LowDeadShadowReason : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461FavAt250ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461FavAt500ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461TimeToFirstProfitMs : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461TimeToMfe10Ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461TimeToMfe20Ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461TimeToMfe40Ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461MfeSlope1sTo3s : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461MaxPullbackAfterFirstProfit : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461HighMidMicroClass : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461HighMidTimeToSpeedMs : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461HighMidFailedReason : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461LowDetectMs : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461LowDetectFav : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461LowDetectSpread : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461LowDetectOrderflowState : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461LowDetectPressureState : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461OppAtEntryMfe : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461OppAtEntryMae : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461OppAtEntryWouldSpeed : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461OppAtEntryNetDelta : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461OppAtLowMfe : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461OppAtLowMae : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461OppAtLowWouldSpeed : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461OppAtLowWouldHardLose : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461OppAtLowNetDelta : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461LowMicroClass : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV461LowMicroClassReason : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47BucketPresent : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47BucketNullReason : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47BucketAuditCloseReason : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47BucketAuditRoute : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47BucketAuditSession : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47BucketAuditSpread : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47BucketAuditFinalPath : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47EntryAvoidShadow : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47500msAvoidShadow : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471sAvoidShadow : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV472sAvoidShadow : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV473sAvoidShadow : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47FirstAvoidTimeMs : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47FirstAvoidStage : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47AvoidReason : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47AvoidReplayDelta : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47WouldBlockLowNoTrade : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47WouldBlockLowUnresolved : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47WouldBlockHigh : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47WouldBlockMid : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47WouldBlockSpeed : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47PreEntryShadowScore : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47PreEntryShadowBucket : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47PreEntryShadowSignals : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47TimeToFirstFavorableTickMs : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47First500msAdverseJump : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47First1sAdverseJump : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47First2sAdverseJump : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV47FrontierNotes : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471SchemaVersion : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471RouteScope : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Alive100ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Alive250ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Alive500ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Alive750ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Alive1s : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Alive1500ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Alive2s : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Alive3s : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Sample100ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Sample250ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Sample500ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Sample750ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Sample1s : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Sample1500ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Sample2s : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Sample3s : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Fav100ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Fav250ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Fav500ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Fav750ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Fav1s : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Fav1500ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Fav2s : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Fav3s : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Ticks100ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Ticks250ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Ticks500ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Ticks750ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Ticks1s : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Ticks1500ms : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Ticks2s : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471Ticks3s : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471First250msAdverseJump : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471First500msAdverseJump : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471First750msAdverseJump : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471First1sAdverseJump : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471First2sAdverseJump : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471TickPath1to8 : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471PreEntryTapeHealth : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471PreEntryVelocityDecay : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471PreSpeedSignalAgeMs : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471FirstFavorableTickState : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471EntryAvoidShadow : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471250msAvoidShadow : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471500msAvoidShadow : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471750msAvoidShadow : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV4711sAvoidShadow : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471FirstAvoidTimeMs : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471FirstAvoidStage : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471AvoidReason : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471AvoidReplayDelta : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471WouldBlockLowNoTrade : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471WouldBlockLowUnresolved : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471WouldBlockHigh : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471WouldBlockMid : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471WouldBlockSpeed : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logV471CoverageNote : ""));
   CsvAdd(row, logV48Mode2Signal);
   CsvAdd(row, logV48Mode2WouldAllow);
   CsvAdd(row, logV48Mode2WouldBlock);
   CsvAdd(row, logV48Mode2BlockReason);
   CsvAdd(row, logV48Mode2OppFlags);
   CsvAdd(row, logV48Mode2Velocity1s);
   CsvAdd(row, logV48Mode2WeightFactor);
   CsvAdd(row, (logRuleTelemetryActive && logRetryCount > 0 ? (string)logRetryCount : ""));
   CsvAdd(row, MeasurementLong(logRuleTelemetryActive, logMsInFrozenState));
   CsvAdd(row, (logRuleTelemetryActive ? logSessionBucket : ""));
   CsvAdd(row, (logRuleTelemetryActive ? logSpreadRegime : ""));
   CsvAdd(row, (logDealLedgerActive ? (string)logDealPositionIdentifier : ""));
   CsvAdd(row, (logDealLedgerActive ? DoubleToString(logDealProfitMoney, 2) : ""));
   CsvAdd(row, (logDealLedgerActive ? DoubleToString(logDealCommissionMoney, 2) : ""));
   CsvAdd(row, (logDealLedgerActive ? DoubleToString(logDealSwapMoney, 2) : ""));
   CsvAdd(row, (logDealLedgerActive ? DoubleToString(logDealFeeMoney, 2) : ""));
   CsvAdd(row, (logDealLedgerActive ? DoubleToString(logDealNetMoney, 2) : ""));
   CsvAdd(row, (logDealLedgerActive ? (logDealCostsComplete ? "true" : "false") : ""));
   CsvAdd(row, (logDealLedgerActive ? (string)logDealLedgerDeals : ""));
   bool closeLifecycleEvent = IsSuccessfulCloseLogEvent(eventName);
   ulong rowPositionTicket = logLifecyclePositionTicket;
   if(rowPositionTicket == 0 && closeLifecycleEvent)
      rowPositionTicket = TicketFromText(reason);
   CsvAdd(row, rowPositionTicket > 0 ? (string)rowPositionTicket : "");
   CsvAdd(row, (string)MagicNumber);
   CsvAdd(row, _Symbol);
   CsvAdd(row, closeLifecycleEvent ? CloseMechanismForLogRow(eventName, reason) : "");
   CsvAdd(row, closeLifecycleEvent && logLifecycleClosePrice > 0.0 ? DoubleToString(logLifecycleClosePrice, _Digits) : "");
   CsvAdd(row, closeLifecycleEvent && logLifecycleCloseServerTimeMsc > 0 ? (string)logLifecycleCloseServerTimeMsc : "");
   CsvAdd(row, closeLifecycleEvent && logLifecycleClosingDealTicket > 0 ? (string)logLifecycleClosingDealTicket : "");
   CsvAdd(row, SAR_LIFECYCLE_RUN_TAG);
   CsvWriteLine(h, row);
   FileClose(h);
   ClearTradeMeasurementContext();
}

//+------------------------------------------------------------------+
void LogInfo(const string eventName, const string reason)
{
   ulong closeTicket = 0;
   bool successfulCloseEvent = IsSuccessfulCloseLogEvent(eventName);
   if(successfulCloseEvent)
   {
      closeTicket = TicketFromText(reason);
      if(IsTicketClosing(closeTicket) || IsCloseLoggedRecently(closeTicket))
      {
         ClearTradeMeasurementContext();
         return;
      }
   }

   DirectionState s;
   ResetState(s);
   s.scenario = "INFO";
   s.labels = reason;
   LogDecision(eventName, ActSkip, s, reason, 0.0, 0.0, 0.0, 0.0);

   if(successfulCloseEvent && closeTicket > 0)
   {
      MarkCloseLogged(closeTicket, eventName);
      MarkTicketClosing(closeTicket, eventName);
      UpdateDefensiveLockoutAfterClose(eventName, reason);
   }
}
//+------------------------------------------------------------------+
void ExecutionAuditWriteHeader()
{
   int h = FileOpen(InpExecutionAuditLogFile,
                    FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI);
   if(h == INVALID_HANDLE)
      return;
   if(FileSize(h) == 0)
      FileWrite(h, "schema_version", "time_msc", "symbol", "magic",
                "event", "side", "details");
   FileClose(h);
}

//+------------------------------------------------------------------+
void ExecutionAuditWrite(const string eventName,
                         const int side,
                         const string details)
{
   int h = FileOpen(InpExecutionAuditLogFile,
                    FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI);
   if(h == INVALID_HANDLE)
      return;
   if(FileSize(h) == 0)
      FileWrite(h, "schema_version", "time_msc", "symbol", "magic",
                "event", "side", "details");
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, "speedalert.execution.audit.v1", (string)GetTickMs(),
             _Symbol, (string)MagicNumber, eventName,
             (side > 0 ? "BUY" : (side < 0 ? "SELL" : "NA")),
             details);
   FileClose(h);
}
//+------------------------------------------------------------------+

#include "CaptureSmoke.mqh"
