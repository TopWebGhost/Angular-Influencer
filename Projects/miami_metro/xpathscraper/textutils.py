import re
import unittest
from collections import defaultdict

import nltk


_re_digits = re.compile(r'[0-9]+')
_re_en_word = re.compile("[A-Z]{2,}(?![a-z])|[A-Z][a-z]+(?=[A-Z])|[\'\w\-]+")


def contains_substring(s, substrings):
    assert isinstance(substrings, (list, tuple))
    return any(ss in s for ss in substrings)

def split_words(s):
    if not s:
        return []
    return re.split(r'\W+', s)

def split_longwords(s):
    '''Use a regexp that doesn't split dots or dashes'''
    if not s:
        return []
    return re.split(r'\s+', s)

def split_en_words(s):
    return _re_en_word.findall(s)

def contains_en_word(s, word):
    return any(w == word.lower() for w in split_en_words(s.lower()))

def contains_any_en_word(s, word_list):
    s_words = split_en_words(s.lower())
    return bool(set(word_list) & set(s_words))

def simple_words(s):
    res = sorted([w.lower() for w in split_words(s)])
    res = [w for w in res if w]
    return res

def simplify(s):
    return ' '.join(split_words(s)).lower()

def simplify_text(s):
    s = remove_nonstandard_chars(s.lower())
    return ' '.join(split_en_words(s))

def contains_digit(s):
    return _re_digits.search(s) is not None

def contains_currency_symbol(s):
    from . import xbrowser
    return any(cs in s for cs in xbrowser.jsonData['currency_symbols'])

def represents_number(s, conv_fun=float):
    try:
        conv_fun(s)
    except ValueError:
        return False
    else:
        return True

def represents_dollar_amount(s):
    return represents_number(s.replace(',', '').replace(' ', ''))

def represents_int(s):
    try:
        int(s)
    except ValueError:
        return False
    else:
        return True

def int_words(s):
    words = split_en_words(s)
    return [w for w in words if represents_int(w)]

def first_int_word(s):
    s = s.strip().replace(',', '').replace('.', '')
    good = int_words(s)
    if good:
        return good[0]
    return None

def remove_nonstandard_chars(s):
    return filter(lambda c: c.isalnum() or c.isspace(), s).strip()

def word_matching_score(s1, s2):
    if not s1 or not s2:
        return 0.0
    s1_words = split_en_words(s1.lower())
    s2_words = split_en_words(s2.lower())
    common_words = len(set(s1_words) & set(s2_words))
    total_words = len(set(s1_words + s2_words))
    return float(common_words) / float(total_words)

def tokenize(s):
    """Default tokenization algorithm."""
    return nltk.wordpunct_tokenize(s)

def tokenize_to_alpha_words(s):
    words = nltk.wordpunct_tokenize(s)
    words = [w for w in words if w.isalpha()]
    return words

def same_word_sets(s1, s2):
    ws1 = nltk.wordpunct_tokenize(s1.lower())
    ws2 = nltk.wordpunct_tokenize(s2.lower())

    as1 = [w for w in ws1 if w.isalpha()]
    as2 = [w for w in ws2 if w.isalpha()]

    if not as1 or not as2:
        return False

    def enough_alpha_words(words, alpha_words):
        return float(len(alpha_words)) / float(len(words)) >= 0.25

    if not enough_alpha_words(ws1, as1) or not enough_alpha_words(ws2, as2):
        return False

    return set(as1) == set(as2)

def is_emoji_char(c):
    return 0x1f300 <= ord(c) <= 0x1f640


class WordSearcher(object):

    def __init__(self, text):
        text = text.lower()
        text_words = nltk.wordpunct_tokenize(text)
        self.index = defaultdict(set)
        for i, word in enumerate(text_words):
            self.index[word].add(i)

    def contains_sentence(self, word_list):
        assert isinstance(word_list, (list, tuple))
        expected_positions = None
        for w in word_list:
            positions = self.index.get(w.lower())
            if not positions:
                return False
            if expected_positions is not None and positions.isdisjoint(expected_positions):
                return False
            expected_positions = {pos+1 for pos in positions}
        return True


class WordSearcherTest(unittest.TestCase):
    
    def testFirstWord(self):
        ws = WordSearcher('aaa bbb ccc')
        self.assertTrue(ws.contains_sentence(['aaa']))

    def testSecondWord(self):
        ws = WordSearcher('aaa bbb ccc')
        self.assertTrue(ws.contains_sentence(['bbb']))

    def testThirdWord(self):
        ws = WordSearcher('aaa bbb ccc')
        self.assertTrue(ws.contains_sentence(['ccc']))

    def testAllWords(self):
        ws = WordSearcher('aaa bbb ccc')
        self.assertTrue(ws.contains_sentence(['aaa', 'bbb', 'ccc']))

    def testAllWordsWrongOrder(self):
        ws = WordSearcher('aaa bbb ccc')
        self.assertFalse(ws.contains_sentence(['ccc', 'bbb', 'aaa']))

    def testMiddleWord(self):
        ws = WordSearcher('a bb ccc')
        self.assertFalse(ws.contains_sentence(['a', 'ccc']))

    def testTwoWords(self):
        ws = WordSearcher('a bb ccc')
        self.assertTrue(ws.contains_sentence(['a', 'bb']))

    def testWordRepeated(self):
        ws = WordSearcher('aaa xxx aaa yyy')
        self.assertTrue(ws.contains_sentence(['aaa', 'xxx']))

    def testUppercase(self):
        ws = WordSearcher('aaa BBB CCc')
        self.assertTrue(ws.contains_sentence(['bbb', 'ccc']))
        self.assertTrue(ws.contains_sentence(['BBB', 'Ccc']))

