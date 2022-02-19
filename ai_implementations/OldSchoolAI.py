from collections import defaultdict, Counter
from functools import lru_cache
from itertools import chain
import math
from random import choice, randint
import re
import string

from WordleAI import WordleAI, LetterInformation
from WordleJudge import WordleJudge


class ContinueException(Exception):
    pass


class OldSchoolAI(WordleAI):

    base_guesses = ('crate', 'loins', 'dumpy', 'wager', 'beefy')
    # base_guesses = ('sorta', 'uncle', 'midgy', 'wheep', 'hijab')
    # base_guesses = ('navel', 'proud', 'thick', 'abysm')
    xcld_wrds_thrs = 100
    xcld_ltrs_thrs = 7
    pop_thrs = 11
    verbose = False

    hard = True

    ROUNDS = 6
    WORD_LENGTH = 5

    FAILED = -1
    ERROR = -2

    def __init__(self, words, **kwargs):

        super().__init__(words)

        self.judge = WordleJudge()
        self.popularity = dict(Counter(chain(*words)))
        self.debug(sorted(self.popularity.items(), key=lambda x: -x[1]))

        for var in ('base_guesses', 'xcld_wrds_thrs', 'xcld_ltrs_thrs', 'pop_thrs', 'verbose', 'hard'):
            setattr(self, var, kwargs.get(var, getattr(self, var)))

    def get_author(self):
        return 'Emma Delescolle (@nanuxbe)'

    def _to_re_str(self, guess, index):
        return ''.join([(guess[index] if x == index else '.') for x in range(len(guess))])

    def debug(self, *args):
        if self.verbose is True:
            print(*args)

    @lru_cache(None)
    def get_valid_guesses(self, guess_history):
        if len(guess_history) == 0:
            return self.words, string.ascii_lowercase, []

        valid_guesses = []

        invalid_letters = []
        valid_letters = []

        valid_expression = defaultdict(lambda: '.')

        invalid_expressions = []

        known_singles = []
        known_doubles = []

        for guess, info in guess_history:
            current_doubles = {
                x: 0
                for x, c in Counter(guess).items()
                if c > 1
            }

            if len(current_doubles) > 0:
                self.debug(guess, current_doubles)

            for i in range(len(guess)):
                if info[i] == LetterInformation.NOT_PRESENT:
                    if guess[i] not in valid_letters and guess[i] not in invalid_letters:
                        invalid_letters.append(guess[i])
                    else:
                        # This a double or triple, ...
                        if guess[i] in valid_letters:
                            # We are only handling doubles
                            if Counter(guess)[guess[i]] == 2 and guess[i] not in known_singles:
                                known_singles.append(guess[i])

                    expression = self._to_re_str(guess, i)
                    invalid_expressions.append(expression)

                elif info[i] in [LetterInformation.PRESENT, LetterInformation.CORRECT]:
                    if guess[i] not in valid_letters:
                        valid_letters.append(guess[i])

                    if current_doubles.get(guess[i], 0) > 0 and guess[i] not in known_doubles:
                        known_doubles.append(guess[i])

                    expression = self._to_re_str(guess, i)
                    if info[i] == LetterInformation.PRESENT:
                        invalid_expressions.append(expression)
                    else:
                        for x in range(len(guess)):
                            if i == x:
                                continue
                            if valid_expression[x] == guess[i] and guess[i] not in known_doubles:
                                known_doubles.append(guess[i])
                        valid_expression[i] = guess[i]

                    if guess[i] in current_doubles:
                        current_doubles[guess[i]] += 1

            for letter in valid_letters:
                if letter in invalid_letters:
                    invalid_letters = [l for l in invalid_letters if l != letter]

        test_invalid_ltrs = len(invalid_letters) > 0
        if test_invalid_ltrs:
            invalid_ltrs_exp = re.compile('[' + ''.join(invalid_letters) + ']')

        invalid_exps = [re.compile(exp) for exp in set(invalid_expressions)]

        valid_exp_str = ''.join([valid_expression[i] for i in range(len(guess_history[0][0]))])
        test_valid_exp = valid_exp_str != '.....'
        if test_valid_exp:
            valid_exp = re.compile(valid_exp_str)

        for word in self.words:
            if test_invalid_ltrs and invalid_ltrs_exp.search(word) is not None:
                continue

            if test_valid_exp and valid_exp.match(word) is None:
                continue

            try:
                for exp in invalid_exps:
                    if exp.match(word) is not None:
                        raise ContinueException
            except ContinueException:
                continue

            try:
                for letter in valid_letters:
                    if letter not in word:
                        raise ContinueException
            except ContinueException:
                continue

            if len(known_singles) > 0 or len(known_doubles) > 0:
                counted = Counter(word)

                try:
                    for letter in known_singles:
                        if counted.get(letter, 0) != 1:
                            raise ContinueException
                except ContinueException:
                    continue

                try:
                    for letter in known_doubles:
                        if counted.get(letter, 0) < 2:
                            raise ContinueException
                except ContinueException:
                    continue

            valid_guesses.append(word)

        if len(valid_guesses) <= 25:
            self.debug(*valid_guesses)
        self.debug('invalid letters', invalid_letters, invalid_ltrs_exp if test_invalid_ltrs else None)
        self.debug('valid letters', valid_letters)
        # self.debug('valid expression', valid_exp_str)
        # self.debug('invalid expressions', invalid_expressions, invalid_exps)
        self.debug(known_singles, known_doubles)

        return valid_guesses, valid_letters, invalid_letters

    @lru_cache(None)
    def _pop_score(self, valid_guesses):
        return sorted(
            valid_guesses,
            key=lambda word: -self.judge.is_wordle_probability(word)
        )

    @lru_cache(None)
    def _score_xcld_words(self, extra_letters, doubles, valid_letters, valid_guesses):
        scored = []
        exp = re.compile('[' + ''.join(extra_letters) + ']')
        self.debug('Exclusion exp', exp)

        for word in self.words:
            if valid_guesses is not None and word not in valid_guesses:
                continue

            score = len(set(exp.findall(word)))

            if score == 0:
                continue

            counted = Counter(word)
            for letter in doubles:
                if counted[letter] > 1:
                    score += .3

            for letter in counted.keys():
                if letter in valid_letters and letter not in doubles:
                    score -= .5

            scored.append((word, score))

        sorted_exclude = sorted(scored, key=lambda x: -x[1])
        if sorted_exclude[0][1] >= 2:
            self.debug(sorted_exclude[:5])
            sorted_dict = dict(sorted_exclude[:5])

            weighted = []
            for word, score in sorted_exclude[:5]:
                counted = Counter(word)

                for letter in counted.keys():
                    if letter in extra_letters and (letter not in valid_letters or counted[letter] > 1):
                        score *= len(self.words) / self.popularity[letter]

                weighted.append((word, score))

            sorted_weighted = sorted(weighted, key=lambda x: -x[1])
            self.debug(sorted_weighted)
            return sorted_weighted[0][0], sorted_dict[sorted_weighted[0][0]]
        else:
            self.debug('Nothing exclusionnary', sorted_exclude[:5])

        return None

    def _xcld_word(self, valid_guesses, valid_letters, invalid_letters):
        extra_letters = []
        doubles = []
        for word in valid_guesses:
            for letter, count in Counter(word).items():
                if letter not in extra_letters + valid_letters + invalid_letters:
                    extra_letters.append(letter)
                elif count > 1 and letter not in extra_letters + invalid_letters:
                    doubles.append(letter)
                    extra_letters.append(letter)

        pruned_xtra_ltrs = []
        for letter in extra_letters:
            val = 2 if letter in doubles else 1
            if all([Counter(word).get(letter, 0) >= val for word in valid_guesses]):
                continue
            pruned_xtra_ltrs.append(letter)

        if 0 < len(pruned_xtra_ltrs) <= self.xcld_ltrs_thrs:
            return self._score_xcld_words(tuple(pruned_xtra_ltrs), tuple(set(doubles)),
                                          tuple(valid_letters), None if not self.hard else tuple(valid_guesses))
        else:
            self.debug(f'Found {len(pruned_xtra_ltrs)} xcl letters')

        return None

    def guess(self, guess_history):

        hashable_history = tuple((guess, tuple(info)) for guess, info in guess_history)

        valid_guesses, valid_letters, invalid_letters = self.get_valid_guesses(hashable_history)

        valid_guesses = tuple(valid_guesses)

        if len(valid_guesses) == 1:
            return valid_guesses[0]

        held_guess = None

        self.debug(f'{len(valid_guesses)} possible matches')
        if (len(valid_guesses) <= 10):
            self.debug(*valid_guesses)

        rounds = self.ROUNDS
        if len(guess_history) > 0:
            rounds = len(guess_history[0][0]) + 1

        rounds_left = rounds - len(guess_history)
        self.debug(f'{rounds_left} rounds left')

        # self.debug(f'{len(valid_guesses)} guesses vs {self.pop_thrs}')
        if 0 < len(valid_guesses) <= self.pop_thrs:
            scored = self._pop_score(valid_guesses)
            if len(valid_guesses) > rounds_left:
                held_guess = scored[0]
                self.debug(f'Holding guess {held_guess}')
            else:
                self.debug('Going for it with most popular match')
                return scored[0]

        if 0 < len(valid_guesses) < self.xcld_wrds_thrs and rounds_left > 1:
            exclusionary_guess = self._xcld_word(valid_guesses, valid_letters, invalid_letters)
            self.debug(f'Computed exclusionary_guess {exclusionary_guess}.')
            if exclusionary_guess is not None and \
                    ((len(valid_letters) == 4 and rounds_left > 2) or (
                        exclusionary_guess[1] >= rounds_left and
                        exclusionary_guess[1] >= 4 * math.sqrt(len(valid_guesses)) / 3
                    )):

                return exclusionary_guess[0]

        if held_guess is not None:
            return held_guess

        if len(guess_history) < len(self.base_guesses):
            if not self.hard or self.base_guesses[len(guess_history)].lower() in valid_guesses:
                return self.base_guesses[len(guess_history)].lower()

        try:
            return choice(valid_guesses)
        except IndexError:
            return self.words[len(guess_history) * 10 + randint(0, 9)]
