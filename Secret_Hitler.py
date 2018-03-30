import random
from enum import Enum
import telegram_integration

GLOBAL_CHAT_ID = None
TESTING = False

class Player(object):
    def __init__(self, _id, _name):
        self.id = _id
        self.name = _name
    def __str__(self):
        return self.name

    def send_message(self, msg):
        # print "[ Message for {} ]\n{}".format(self, msg)
        telegram_integration.bot.send_message(chat_id=self.id, text=msg)

    def set_role(self, _role):
        self.role = _role
        self.party = _role.replace("Hitler", "Fascist")
        self.send_message("Your secret role is {}".format(self.role))

class GameStates(Enum):
    ACCEPT_PLAYERS = 1
    CHANCY_NOMINATION = 2
    ELECTION = 3
    LEG_PRES = 4
    LEG_CHANCY = 5
    VETO_CHOICE = 6
    INVESTIGATION = 7
    SPECIAL_ELECTION = 8
    EXECUTION = 9
    GAME_OVER = 10
class GameOverException(Exception):
    pass

class Game(object):
    def __init__(self, chat_id):
        if TESTING:
            self.deck = ['F', 'F', 'L', 'F', 'F', 'L', 'F', 'F', 'L', 'F', 'F', 'L', 'F', 'F', 'L', 'F', 'L']
        else:
            self.deck = ['L', 'L', 'L', 'L', 'L', 'L',
                        'F', 'F', 'F', 'F', 'F', 'F', 'F', 'F', 'F', 'F', 'F']
            random.shuffle(self.deck)

        self.global_chat = chat_id

        self.discard = []

        self.players = []
        self.president = None
        self.chancellor = None
        self.termlimited_players = set()
        self.dead_players = set()
        # TODO: track CNH

        self.last_nonspecial_president = None
        self.vetoable_polcy = None
        self.president_veto_vote = None
        self.chancellor_veto_vote = None

        self.num_players = 0

        self.votes = []
        self.liberal = 0
        self.fascist = 0
        self.anarchy_progress = 0

        self.game_state = GameStates.ACCEPT_PLAYERS
    def start_game(self):
        # random.shuffle(self.players)
        # NOTE: players will be seated in order they join unless this is uncommented

        self.num_players = len(self.players)
        self.num_alive_players = self.num_players
        self.num_dead_players = 0

        if self.num_players == 5 or self.num_players == 6: # 1F + H
            fascists = random.sample(self.players, 2)
        elif self.num_players == 7 or self.num_players == 8: # 2F + H
            fascists = random.sample(self.players, 3)
        elif self.num_players == 9 or self.num_players == 10: # 3F + H
            fascists = random.sample(self.players, 4)
        else:
            raise Exception("Invalid number of players")

        for p in self.players:
            if p == fascists[0]:
                p.set_role("Hitler")
                if self.num_players <= 6:
                    p.send_message("Fascist: {}".format(fascists[1]))
            elif p in fascists:
                p.set_role("Fascist")
                if self.num_players <= 6:
                    p.send_message("Hitler: {}".format(fascists[0]))
                else:
                    p.send_message("Other Fascist{}: {}\nHitler: {}".format("s" if len(fascists) > 3 else "", ", ".join([ other_p.name for other_p in fascists[1:] if other_p != p ]), fascists[0]))
            else:
                p.set_role("Liberal")

        self.president = self.players[0]
        self.set_game_state(GameStates.CHANCY_NOMINATION)

    @staticmethod
    def str_to_vote(vote_str):
        vote_str = vote_str.lower()
        if vote_str in ("ja", "yes", "y"):
            return True
        elif vote_str in ("nein", "no", "n"):
            return False
        else:
            return None
    @staticmethod
    def str_to_policy(vote_str):
        vote_str = vote_str.lower()
        if vote_str == "f" or vote_str.find("s p i c y") != -1 or vote_str == "fascist":
            return "F"
        elif vote_str == "l" or vote_str.find("") != -1 or vote_str == "lib":
            return "L"
        else:
            return None
    def global_message(self, msg):
        # print "[ Message for everyone ]\n{}".format(msg)
        telegram_integration.bot.send_message(chat_id=self.global_chat, text=msg)
    def str_to_player(self, player_str):
        if player_str.isdigit() and int(player_str) > 0 and int(player_str) <= self.num_players:
            return self.players[int(player_str) - 1]
        else:
            for p in self.players:
                if p.name.find(player_str) != -1:
                    return p
            return None
    def id_to_player(self, id):
        for p in self.players:
            if p.id == id:
                return p
        return None
    def list_players(self):
        ret = ""
        for i in range(len(self.players)):
            status = ""
            if self.players[i] == self.president:
                status += " (P)"
            if self.players[i] == self.chancellor:
                status += " (C)"
            if self.players[i] in self.termlimited_players:
                status += " (TL)"
            if self.players[i] in self.dead_players:
                status += " (RIP)"
            ret += "({}) {}{}\n".format(i + 1, self.players[i], status)

        return ret
    def add_player(self, p):
        self.players.append(p)
        self.votes.append(None)
        self.num_players += 1
    def remove_player(self, p):
        if self.game_state == GameStates.ACCEPT_PLAYERS:
            self.players.remove(p)
            self.votes.pop()
            self.num_players -= 1
        elif p in self.dead_players: # TODO probably unnecessary
            index = self.players.index(p)
            self.players.pop(index)
            self.votes.pop(index)
            self.num_players -= 1
            self.num_dead_players -= 1
        else:
            self.global_message("Player {} left, so this game is self-destructing".format(p))
            self.set_game_state(GameStates.GAME_OVER)

    def select_chancellor(self, target):
        if target in self.termlimited_players or target in self.dead_players or target == self.president:
            return False
        else:
            self.chancellor = target

            self.global_message("President {} has nominated Chancellor {}.".format(self.president, self.chancellor))
            #self.global_message("Now voting on {}/{}".format(self.president, self.chancellor))
            self.set_game_state(GameStates.ELECTION)

            return True

    def cast_vote(self, player, vote):
        self.players[self.players.index(player)] = vote
    def list_nonvoters(self):
        return "\n".join([ str(self.players[i]) for i in range(self.num_players) if self.votes[i] is None ])
    def election_is_done(self):
        return self.votes.count(None) == self.num_dead_players
    def election_call(self):
        if self.votes.count(True) > self.num_alive_players / 2:
            return True
        elif self.votes.count(False) >= self.num_alive_players / 2:
            return False
        else:
            return None
    def election_results(self):
        return "\n".join([ "{} - {}".format(self.players[i], "ja" if self.votes[i] else "nein") for i in range(self.num_players) if self.players[i] not in self.dead_players])
    def update_termlimits(self):
        self.termlimited_players.clear()
        self.termlimited_players.add(self.chancellor)
        if self.num_players - len(self.dead_players) > 5:
            self.termlimited_players.add(self.president)

    def end_election(self):
        assert self.election_is_done()
        election_result = self.election_call()

        self.global_message("{}".format("JA!" if election_result else "NEIN!"))
        self.global_message(self.election_results())

        if election_result:
            if self.fascist >= 3 and self.chancellor.role == "Hitler":
                self.end_game("Fascist", "Hitler was elected chancellor")
            else:
                self.set_game_state(GameStates.LEG_PRES)

            self.update_termlimits()
            self.anarchy_progress = 0
        else:
            self.anarchy_progress += 1
            if self.anarchy_progress == 3:
                self.anarchy()

            self.advance_presidency()

        self.votes = [None] * self.num_players

    def president_legislate(self, discard):
        if discard in self.deck[:3]:
            self.deck.remove(discard)
            self.discard.append(discard)

            self.set_game_state(GameStates.LEG_CHANCY)
            return True
        else:
            return False
    def chancellor_legislate(self, enact):
        if enact in self.deck[:2]:
            self.deck.remove(enact)
            self.discard.append(self.deck.pop(0))

            if self.fascist == 5:
                self.vetoable_polcy = enact
                self.set_game_state(GameStates.VETO_CHOICE)
            else:
                self.pass_policy(enact)
            return True
        else:
            return False
    def check_reshuffle(self):
        if len(self.deck) <= 3: # NOTE: official rules say not to shuffle when there are 3 policies but this is a house rule
            self.deck.extend(self.discard)
            del self.discard[:]

            random.shuffle(self.deck)

            self.global_message("Deck has been reshuffled.")

    def check_veto(self):
        if False in (self.president_veto_vote, self.chancellor_veto_vote): # no veto
            if self.president_veto_vote is False:
                non_vetoer = "President " + str(self.president)
            else:
                non_vetoer = "Chancellor " + str(self.chancellor)

            self.global_message("{} has refused to veto".format(non_vetoer))
            self.pass_policy(self.vetoable_polcy)
            self.vetoable_polcy = None
            self.advance_presidency()
        elif self.president_veto_vote and self.chancellor_veto_vote: # veto
            self.global_message("VETO!")

            self.discard.append(self.vetoable_polcy)
            self.check_reshuffle()
            self.vetoable_polcy = None
            self.anarchy_progress

            self.anarchy_progress += 1
            if self.anarchy_progress == 3:
                self.anarchy()

    def pass_policy(self, policy, on_anarchy=False):
        if policy == "L":
            self.pass_liberal()
        else:
            self.pass_fascist(on_anarchy)

        if self.game_state == GameStates.GAME_OVER:
            return

        self.global_message("BOARD STATE\n{} Fascist\n{} Liberal".format(self.fascist, self.liberal))

        self.check_reshuffle()
        if not on_anarchy and self.game_state == GameStates.LEG_CHANCY: # don't need to wait for other decisison
            self.advance_presidency()
    def pass_liberal(self):
        self.liberal += 1
        self.global_message("A liberal policy was passed!")

        if self.liberal == 5:
            self.end_game("Liberal", "5 Liberal policies were enacted")
    def pass_fascist(self, on_anarchy):
        self.fascist += 1
        self.global_message("A fascist policy was passed!")

        if self.fascist == 6:
            self.end_game("Fascist", "6 Fascist policies were enacted")

        if on_anarchy:
            return # any executive powers ignored in anarchy

        if self.num_players in (5,6) and self.fascist == 3:
            self.check_reshuffle()
            self.global_message("President ({}) is examining top 3 policies".format(self.president))
            self.president.send_message("Top three policies are: ")
            self.deck_peek(self.president, 3)
        else:
            if self.fascist == 2 or (self.fascist == 1 and self.num_players >= 9):
                self.set_game_state(GameStates.INVESTIGATION)
            elif self.fascist == 3:
                self.set_game_state(GameStates.SPECIAL_ELECTION)

        if self.fascist == 4 or self.fascist == 5:
            self.set_game_state(GameStates.EXECUTION)
    def next_alive_player(self, starting_after):
        target_index = self.players.index(starting_after)
        while self.players[target_index] == starting_after or self.players[target_index] in self.dead_players:
            target_index += 1
            target_index %= self.num_players
        return self.players[target_index]

    def advance_presidency(self):
        if self.last_nonspecial_president == None:
            self.president = self.next_alive_player(self.president)
        else:
            self.president = self.next_alive_player(self.last_nonspecial_president)
            self.last_nonspecial_president = None

        self.chancellor = None
        self.set_game_state(GameStates.CHANCY_NOMINATION)

    def investigate(self, origin, target):
        origin.send_message("<{0}> party affiliation is <{0.party}>".format(target))
        self.global_message("{} has investigated {}".format(self, target))
    def deck_peek(self, who, num=3):
        who.send_message("".join(self.deck[:num]))
    def special_elect(self, target):
        if target == self.president:
            return False # cannot special elect self

        self.last_nonspecial_president = self.president
        self.president = target
        return True

    def kill(self, target):
        if target.role == "Hitler":
            self.end_game("Liberal", "Hitler was killed")
        else:
            self.dead_players.add(target)
            self.num_alive_players -= 1
            self.num_dead_players += 1

    def anarchy(self):
        self.check_reshuffle()
        self.pass_policy(self.deck.pop(0), on_anarchy=True)

        self.termlimited_players.clear()
        self.anarchy_progress = 0

    def end_game(self, winning_party, reason):
        self.global_message("The {} team wins! ({}.)".format(winning_party, reason))
        self.set_game_state(GameStates.GAME_OVER)
        raise GameOverException("The {} team wins! ({}.)".format(winning_party, reason))

    def set_game_state(self, new_state):
        self.game_state = new_state

        if self.game_state == GameStates.CHANCY_NOMINATION:
            self.global_message("President {} must nominate a chancellor".format(self.president))
            self.president.send_message("Pick your chancellor:\n" + self.list_players())
        elif self.game_state == GameStates.ELECTION:
            self.global_message("Election: Vote on President {} and Chancellor {}".format(self.president, self.chancellor))
            for p in self.players: # send individual messages to clarify who you're voting on
                if p not in self.dead_players:
                    p.send_message("{}/{} vote:".format(self.president, self.chancellor))
        elif self.game_state == GameStates.LEG_PRES:
            self.global_message("Legislative session in progress (waiting on President {})".format(self.president))
            self.president.send_message("Pick a policy to discard:")
            self.deck_peek(self.president, 3)
        elif self.game_state == GameStates.LEG_CHANCY:
            self.global_message("Legislative session in progress (waiting on Chancellor {})".format(self.chancellor))
            self.chancellor.send_message("Pick a policy to enact:")
            self.deck_peek(self.chancellor, 2)
        elif self.game_state == GameStates.VETO_CHOICE:
            self.global_message("President ({}) and Chancellor ({}) are deciding whether to veto (both must agree to do so)".format(self.president, self.chancellor))
            self.president.send_message("Would you like to veto?")
            self.chancellor.send_message("Would you like to veto?")
            self.president_veto_vote = None
            self.chancellor_veto_vote = None
        elif self.game_state == GameStates.INVESTIGATION:
            self.global_message("President ({}) must investigate another player".format(self.president))
            self.president.send_message("Pick a player to investigate:\n" + self.list_players())
        elif self.game_state == GameStates.SPECIAL_ELECTION:
            self.global_message("Special Election: President ({}) must choose the next presidential candidate".format(self.president))
            self.president.send_message("Pick the next presidential candidate:\n" + self.list_players())
        elif self.game_state == GameStates.EXECUTION:
            self.global_message("President ({}) must kill someone".format(self.president))
            self.president.send_message("Pick someone to kill:\n" + self.list_players())
        elif self.game_state == GameStates.GAME_OVER:
            self.global_message("\n".join(["{} - {}".format(p, p.role) for p in self.players]))
            # reveal all player roles when the game has ended

    ACCEPTED_COMMANDS = ("listplayers", "changename", "joingame", "leave", "startgame",
        "boardstats", "deckstats", "anarchystats", "blame", "ja", "nein",
        "nominate", "kill", "investigate", "enact", "discard")
    def handle_message(self, from_player, command, args):
        # commands valid at any time
        if command == "listplayers":
            return self.list_players()
        elif command == "changename":
            if from_player in self.players:
                from_player.name = args
                return "Successfully changed name to '{}'".format(args)
            else:
                return "Must be in game to change nickname"
        elif self.game_state == GameStates.ACCEPT_PLAYERS:
            if command == "joingame":
                if self.num_players == 10:
                    return "Error: game is full"
                elif from_player in self.players:
                    return "Error: you've already joined"
                self.add_player(from_player)
                return "{}, Welcome to Secret Hitler!".format(from_player.name)
            elif command == "leave":
                self.remove_player(from_player)
                return "Successfully left game!"
            elif command == "startgame":
                if self.num_players >= 5:
                    self.start_game()
                    return
                else:
                    return "Error: only {} players".format(self.num_players)
            else:
                return "Error: game has not started"
        if command == "boardstats":
            return "{} Fascist / {} Liberal".format(self.fascist, self.liberal)
        elif command == "deckstats":
            return "{} tiles in deck, {} in discard. {} F / {} L in deck/discard (combined)".format(len(self.deck), len(self.discard), 11 - self.fascist, 6 - self.liberal)
        elif command == "anarchystats":
            return "Election tracker is at {}/3".format(self.anarchy_progress)
        elif command == "blame" and self.game_state == GameStates.ELECTION:
            return "People who haven't yet voted:\n" + self.list_nonvoters()
        elif from_player not in self.players or from_player in self.dead_players:
            return "Error: Spectators/dead players cannot use commands that modify game data"
            # further commands affect game state
        elif command in ("nominate", "kill", "investigate") and from_player == self.president:
            # commands that involve the president selecting another player
            target = self.str_to_player(args)
            if target == None and not (command == "kill" and target.find("me too thanks") != -1 and self.game_state == GameStates.EXECUTION):
                return "Error: Could not parse player."
            if command == "nominate":
                if self.game_state == GameStates.CHANCY_NOMINATION:
                    if self.select_chancellor(new_chancellor):
                        return None # "You have nominated {} for chancellor.".format(target)
                    else:
                        return "Error: {} is term-limited/dead/yourself.".format(new_chancellor)
                elif self.game_state == GameStates.SPECIAL_ELECTION:
                    if self.special_elect(target):
                        self.set_game_state(GameStates.CHANCY_NOMINATION)
                        return None # "You have nominated {} for president.".format(target)
                    else:
                        return "Error: you can't nominate yourself for president.".format(target)
            elif command == "kill" and self.game_state == GameStates.EXECUTION:
                if from_player == target:
                    from_player.send_message("You are about to kill yourself.  This is technically allowed by the rules, but why are you like this?")
                    from_player.send_message("Reply 'me too thanks' to confirm suicide")
                elif args.find("me too thanks") != -1:
                    self.kill(from_player)
                    self.advance_presidency()
                    return "You have killed yourself."
                else:
                    self.kill(target)
                    self.advance_presidency()
                    from_player.send_message("You have killed {}.".format(target))
            elif command == "investigate" and self.game_state == GameStates.INVESTIGATION:
                self.investigate(from_player, target)
                self.advance_presidency()
        elif command in ("ja", "nein"):
            vote = (command == "ja")
            if self.game_state == GameStates.ELECTION:
                self.votes[self.players.index(from_player)] = vote

                if self.election_is_done():
                    self.end_election()
                    return None
                else:
                    if vote:
                        return "Ja vote recorded; quickly /nein to switch"
                    else:
                        return "Nein vote recorded; quickly /ja to switch"
            elif self.game_state == GameStates.VETO_CHOICE and from_player in (self.president, self.chancellor):
                if from_player == self.president:
                    self.president_veto_vote = vote
                elif from_player == self.chancellor:
                    self.chancellor_veto_vote = vote

                self.check_veto()
                return "Veto vote recorded"
            # TODO: expedite the game by giving pres/chancy their policies before the election is finished
        elif command in ("enact", "discard"):
            policy = Game.str_to_policy(args)
            if policy is None:
                return "Error: Policy could not be parsed"

            if command == "discard" and self.game_state == GameStates.LEG_PRES and from_player == self.president:
                if self.president_legislate(policy):
                    return None # "Thanks"
                else:
                    return "Error: Given policy not in top 3"
            elif self.game_state == GameStates.LEG_CHANCY and from_player == self.chancellor:
                if command == "discard" and self.deck[0] != self.deck[1]:
                    policy = "L" if policy == "F" else "F"

                if self.chancellor_legislate(policy):
                    return None
                    # if self.fascist < 5: # prevents "thanks" from happening after veto notification
                    #     return "Thanks!"
                else:
                    return "Error: Given policy not in top 2"

# if TESTING:
#     game = Game()
#     game.add_player(Player("1", "A"))
#     game.add_player(Player("2", "B"))
#     game.add_player(Player("3", "C"))
#     game.add_player(Player("4", "D"))
#     game.add_player(Player("5", "E"))
#     game.add_player(Player("6", "F"))
#     game.add_player(Player("7", "G"))
#     game.handle_message("3", "/startgame")
#
#     game.handle_message("1", "D") # 1
#
#     game.handle_message("1", "ja")
#     game.handle_message("2", "ja")
#     game.handle_message("3", "ja")
#     game.handle_message("4", "nein")
#     game.handle_message("5", "ja")
#     game.handle_message("6", "nein")
#     game.handle_message("7", "ja")
#
#     game.handle_message("1", "L")
#     #game.handle_message("1", "F")
#     game.handle_message("4", "F")
#     #game.handle_message("4", "L")
#
#     game.handle_message("2", "E") # 2
#
#     game.handle_message("1", "ja")
#     game.handle_message("2", "ja")
#     game.handle_message("3", "ja")
#     game.handle_message("4", "nein")
#     game.handle_message("5", "ja")
#     game.handle_message("6", "nein")
#     game.handle_message("7", "ja")
#
#     game.handle_message("2", "L")
#     #game.handle_message("2", "F")
#     game.handle_message("5", "F")
#     #game.handle_message("5", "L")
#
#     game.handle_message("2", "E") # inv
#
#     game.handle_message("3", "F") # 3
#
#     game.handle_message("1", "ja")
#     game.handle_message("2", "ja")
#     game.handle_message("3", "ja")
#     game.handle_message("4", "nein")
#     game.handle_message("5", "ja")
#     game.handle_message("6", "nein")
#     game.handle_message("7", "ja")
#
#     game.handle_message("3", "L")
#     #game.handle_message("3", "F")
#     game.handle_message("6", "F")
#     #game.handle_message("6", "L")
#
#     game.handle_message("3", "B") # se
#
#     game.handle_message("2", "G") # 4
#
#     game.handle_message("1", "ja")
#     game.handle_message("2", "ja")
#     game.handle_message("3", "ja")
#     game.handle_message("4", "nein")
#     game.handle_message("5", "ja")
#     game.handle_message("6", "nein")
#     game.handle_message("7", "ja")
#
#     game.handle_message("2", "L")
#     #game.handle_message("4", "F")
#     game.handle_message("7", "F")
#     #game.handle_message("7", "L")
#
#     game.handle_message("2", "me too thanks") # execution
#
#     game.handle_message("4", "A") # nein
#
#     game.handle_message("1", "nein")
#     game.handle_message("3", "ja")
#     game.handle_message("4", "nein")
#     game.handle_message("5", "nein")
#     game.handle_message("6", "ja")
#     game.handle_message("7", "ja")
#
#     game.handle_message("5", "A") # nein
#
#     game.handle_message("1", "nein")
#     game.handle_message("3", "ja")
#     game.handle_message("4", "nein")
#     game.handle_message("5", "nein")
#     game.handle_message("6", "ja")
#     game.handle_message("7", "ja")
#
#     game.handle_message("6", "A") # nein
#
#     game.handle_message("1", "nein")
#     game.handle_message("3", "ja")
#     game.handle_message("4", "nein")
#     game.handle_message("5", "nein")
#     game.handle_message("6", "ja")
#     game.handle_message("7", "ja")
#
#     # anarchy
#
#     game.handle_message("7", "A") # nein
#
#     game.handle_message("1", "ja")
#     game.handle_message("3", "ja")
#     game.handle_message("4", "nein")
#     game.handle_message("5", "nein")
#     game.handle_message("6", "ja")
#     game.handle_message("7", "ja")
#
#     game.handle_message("7", "f")
#     game.handle_message("1", "l")
#
#     #veto decisison
#     game.handle_message("1", "ja")
#     game.handle_message("7", "nein")
#
#     game.handle_message("1", "D") # Fasc victory
#
#     game.handle_message("1", "ja")
#     game.handle_message("3", "ja")
#     game.handle_message("4", "nein")
#     game.handle_message("5", "nein")
#     game.handle_message("6", "ja")
#     game.handle_message("7", "ja")
#
#     game.handle_message("1", "l")
#     game.handle_message("4", "f")
#
#     #veto decisison
#     game.handle_message("1", "nein")
#     #game.handle_message("7", "ja")
