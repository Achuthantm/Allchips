from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction
from skeleton.states import GameState, TerminalState, RoundState
from skeleton.states import NUM_ROUNDS, STARTING_STACK, BIG_BLIND, SMALL_BLIND
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot
import sys
import os
import joblib
import __main__
import contextlib

# Redirect stdout to stderr aggressively
sys.stdout = sys.stderr

# Monkeypatch pyttsx3 to prevent engine initialization crashes (audio driver issues in CLI)
class MockEngine:
    def say(self, *args, **kwargs): pass
    def runAndWait(self, *args, **kwargs): pass
    def stop(self, *args, **kwargs): pass
    def setProperty(self, *args, **kwargs): pass
    def getProperty(self, *args, **kwargs): return None

try:
    import pyttsx3
    pyttsx3.init = lambda *args, **kwargs: MockEngine()
except ImportError:
    sys.modules['pyttsx3'] = type('Module', (), {'init': lambda *args, **kwargs: MockEngine()})

# Add Poker-AI/src to sys.path
POKER_AI_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'pokerai', 'Poker-AI', 'src'))
if POKER_AI_SRC not in sys.path:
    sys.path.insert(0, POKER_AI_SRC)

# Pre-import modules and fix abstraction settings
import player
import evaluator
original_cwd = os.getcwd()
os.chdir(POKER_AI_SRC)
try:
    import abstraction
    abstraction.USE_KMEANS = False
    abstraction.NUM_FLOP_CLUSTERS = 10
    abstraction.NUM_TURN_CLUSTERS = 10
    abstraction.NUM_RIVER_CLUSTERS = 10
finally:
    os.chdir(original_cwd)

import base
try:
    import preflop_holdem
    import postflop_holdem
    __main__.PreflopHoldemInfoSet = preflop_holdem.PreflopHoldemInfoSet
    __main__.PostflopHoldemInfoSet = postflop_holdem.PostflopHoldemInfoSet
    __main__.PreflopHoldemHistory = preflop_holdem.PreflopHoldemHistory
    __main__.PostflopHoldemHistory = postflop_holdem.PostflopHoldemHistory
    __main__.InfoSet = base.InfoSet
    __main__.History = base.History
except ImportError as e:
    print(f"Error importing Holdem modules: {e}", file=sys.stderr)

from aiplayer import CFRAIPlayer
from evaluator import Card

class FixedCFRAIPlayer(CFRAIPlayer):
    def __init__(self, balance, model_dir):
        from player import Player as PokerAIBasePlayer
        PokerAIBasePlayer.__init__(self, balance)
        self.is_AI = True
        self.speak = False
        self.engine = MockEngine()
        self.preflop_infosets = joblib.load(os.path.join(model_dir, "preflop_infoSets_batch_19.joblib"))
        self.postflop_infosets = joblib.load(os.path.join(model_dir, "postflop_infoSets_batch_19.joblib"))

    def trash_talk_win(self): pass
    def trash_talk_lose(self): pass
    def trash_talk_fold(self): pass
    def process_action(self, action, observed_env): pass

class Player(Bot):
    def __init__(self):
        self.ai_player = FixedCFRAIPlayer(STARTING_STACK, POKER_AI_SRC)
        self.history = []
        self.last_street = 0
        self.last_pips = [SMALL_BLIND, BIG_BLIND]

    def handle_new_round(self, game_state, round_state, active):
        self.ai_player.playing_current_round = True
        self.ai_player.current_bet = 0
        self.ai_player.clear_hand()
        my_cards = "".join([str(c) for c in round_state.hands[active]])
        placeholder_opp = "AhAd" 
        if active == 0: self.history = [placeholder_opp, my_cards]
        else: self.history = [my_cards, placeholder_opp]
        self.last_street = 0
        self.last_pips = [SMALL_BLIND, BIG_BLIND]

    def handle_round_over(self, game_state, terminal_state, active): pass

    def sync_history(self, round_state, active):
        opp = 1 - active
        # 1. Handle Street Transitions
        if round_state.street != self.last_street:
            if len(self.history) > 0:
                last_act = self.history[-1]
                # Detect actions that ended the previous street
                if self.last_pips[opp] < self.last_pips[active]:
                    self.history.append('c') # Opponent called our bet
                elif self.last_pips[opp] == self.last_pips[active]:
                    if self.last_street > 0: # Post-flop
                        if active == 1 and last_act == 'k': self.history.append('k') # SB checked back
                    else: # Pre-flop
                        if active == 0 and last_act == 'c': self.history.append('k') # BB checked back

            self.history.append('/')
            board = ""
            if round_state.street == 3: board = "".join(round_state.deck[:3])
            elif round_state.street == 4: board = round_state.deck[3]
            elif round_state.street == 5: board = round_state.deck[4]
            if board: self.history.append(board)
            self.last_street = round_state.street
            self.last_pips = [0, 0]
            if round_state.street == 0: self.last_pips = [SMALL_BLIND, BIG_BLIND]

        # 2. Detect first actor's move on current street (Post-flop BB acts first)
        if round_state.street > 0 and active == 0:
            if self.history[-1].isalnum() and len(self.history[-1]) in [2, 6]:
                if round_state.pips[1] > 0: self.history.append('b' + str(round_state.pips[1]))
                else: self.history.append('k')

        # 3. Detect subsequent opponent actions
        if round_state.pips[opp] > self.last_pips[opp]:
            if round_state.pips[opp] == round_state.pips[active] and round_state.pips[opp] > 0:
                self.history.append('c')
            else:
                self.history.append('b' + str(round_state.pips[opp]))
        
        self.last_pips = list(round_state.pips)

    def get_action(self, game_state, round_state, active):
        self.sync_history(round_state, active)
        street = round_state.street
        my_cards_str = [str(c) for c in round_state.hands[active]]
        board_cards_str = [str(c) for c in round_state.deck[:street]]
        self.ai_player.hand = [Card(c) for c in my_cards_str]
        
        my_pip, opp_pip = round_state.pips[active], round_state.pips[1-active]
        total_pot = (STARTING_STACK - round_state.stacks[active]) + (STARTING_STACK - round_state.stacks[1-active])
        
        check_allowed = CheckAction in round_state.legal_actions()
        with contextlib.redirect_stdout(sys.stderr):
            try:
                action_str = self.ai_player.get_action(
                    history=self.history, card_str=my_cards_str, community_cards=board_cards_str,
                    highest_current_bet=max(my_pip, opp_pip), stage_pot_balance=my_pip + opp_pip,
                    total_pot_balance=total_pot, player_balance=round_state.stacks[active] + my_pip,
                    BIG_BLIND=BIG_BLIND, isDealer=(active == 0), checkAllowed=check_allowed
                )
            except Exception as e:
                print(f"GTO error {e}, fallback", file=sys.stderr)
                action_str = 'k' if check_allowed else 'c'
        
        self.history.append(action_str)
        if action_str == 'f': return FoldAction()
        if action_str == 'k': 
            self.last_pips[active] = round_state.pips[active]
            return CheckAction()
        if action_str == 'c':
            self.last_pips[active] = round_state.pips[1-active]
            return CallAction()
        if action_str.startswith('b'):
            try: amount = int(action_str[1:])
            except: amount = BIG_BLIND
            if RaiseAction in round_state.legal_actions():
                low, high = round_state.raise_bounds()
                amount = max(low, min(high, amount))
                self.last_pips[active] = amount
                return RaiseAction(amount)
            return CheckAction() if check_allowed else CallAction()
        return CheckAction() if check_allowed else CallAction()

if __name__ == '__main__':
    run_bot(Player(), parse_args())
