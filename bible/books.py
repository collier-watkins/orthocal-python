def normalize_book_name(name):
    cleaned = ' '.join(name.split()).replace('.', '').lower()
    return BOOK_NAMES.get(cleaned, '')

def is_chapterless(book):
    return book in CHAPTERLESS_BOOKS

# This is populated by AppConfig.ready()
CHAPTERLESS_BOOKS = None

BOOK_NAMES = {
	# Old Testament
	'gen':             'GEN',
	'genesis':         'GEN',
	'exod':            'EXO',
	'exodus':          'EXO',
	'lev':             'LEV',
	'leviticus':       'LEV',
	'num':             'NUM',
	'numbers':         'NUM',
	'deut':            'DEU',
	'deuteronomy':     'DEU',
	'josh':            'JOS',
	'joshua':          'JOS',
	'judges':          'JDG',
	'judg':            'JDG',
	'ruth':            'RUT',
	'1 kgs':           '1SA',
	'1 kings':         '1SA',
	'2 kgs':           '2SA',
	'2 kings':         '2SA',
	'3 kgs':           '1KI',
	'3 kings':         '1KI',
	'4 kgs':           '2KI',
	'4 kings':         '2KI',
	'1 chr':           '1CH',
	'1 chronicles':    '1CH',
	'2 chr':           '2CH',
	'2 chronicles':    '2CH',
	'ezra':            'EZR',
	'neh':             'NEH',
	'nehemiah':        'NEH',
	'esth':            'EST',
	'esther':          'EST',
	'job':             'JOB',
	'ps':              'PSA',
	'psalm':           'PSA',
	'psalms':          'PSA',
	'prov':            'PRO',
	'proverbs':        'PRO',
	'eccl':            'ECC',
	'ecclesiastes':    'ECC',
	'song':            'SNG',
	'song of solomon': 'SNG',
	'song of songs':   'SNG',
	'isa':             'ISA',
	'isaiah':          'ISA',
	'jer':             'JER',
	'jeremiah':        'JER',
	'hos':             'HOS',
	'hosea':           'HOS',
	'joel':            'JOL',
	'amos':            'AMO',
	'obad':            'OBA',
	'obadiah':         'OBA',
	'jonah':           'JON',
	'jon':             'JON',
	'mic':             'MIC',
	'micah':           'MIC',
	'nah':             'NAM',
	'nahum':           'NAM',
	'hab':             'HAB',
	'habakkuk':        'HAB',
	'zech':            'ZEC',
	'zechariah':       'ZEC',
	'hag':             'HAG',
	'hagai':           'HAG',
	'lam':             'LAM',
	'lamentations':    'LAM',
	'ezek':            'EZK',
	'ezekiel':         'EZK',
	'dan':             'DAN',
	'daniel':          'DAN',
	'zeph':            'ZEP',
	'zephaniah':       'ZEP',
	'mal':             'MAL',
	'malachi':         'MAL',

	# Deuterocanonical
	'tobit':                  'TOB',
	'tob':                    'TOB',
	'judith':                 'JDT',
	'additions to esther':    'ESG',
	'wis':                    'WIS',
	'wisdom':                 'WIS',
	'wisdom of solomon':      'WIS',
	'sirach':                 'SIR',
	'ecclesiasticus':         'SIR',
	'wisdom of sirach':       'SIR',
	'baruch':                 'BAR',
	'letter of jeremiah':     'LJE',
	'song of the three':      'S3Y',
	'prayer of azariah':      'S3Y',
	'susanna':                'SUS',
	'bel and the dragon':     'BEL',
	'1 maccabees':            '1MA',
	'2 maccabees':            '2MA',
	'3 maccabees':            '3MA',
	'4 maccabees':            '4MA',
	'1 esdras':               '1ES',
	'2 esdras':               '2ES',
	'manasseh':               'MAN',
	'the prayer of manasseh': 'MAN',

	# New Testament
	'matt':            'MAT',
	'matthew':         'MAT',
	'mt':              'MAT',
	'mark':            'MRK',
	'mk':              'MRK',
	'luke':            'LUK',
	'lk':              'LUK',
	'john':            'JHN',
	'jn':              'JHN',
	'acts':            'ACT',
	'rom':             'ROM',
	'1 cor':           '1CO',
	'1 corinthians':   '1CO',
	'2 cor':           '2CO',
	'2 corinthians':   '2CO',
	'1 thess':         '1TH',
	'1 thessalonians': '1TH',
	'2 thess':         '2TH',
	'2 thessalonians': '2TH',
	'gal':             'GAL',
	'galatians':       'GAL',
	'eph':             'EPH',
	'ephesians':       'EPH',
	'phil':            'PHP',
	'philippians':     'PHP',
	'col':             'COL',
	'colosians':       'COL',
	'1 tim':           '1TI',
	'1 timothy':       '1TI',
	'2 tim':           '2TI',
	'2 timothy':       '2TI',
	'1 john':          '1JN',
	'1 jn':            '1JN',
	'2 john':          '2JN',
	'2 jn':            '2JN',
	'3 john':          '3JN',
	'3 jm':            '3JN',
	'1 pet':           '1PE',
	'1 peter':         '1PE',
	'2 pet':           '2PE',
	'2 peter':         '2PE',
	'heb':             'HEB',
	'hebrews':         'HEB',
	'titus':           'TIT',
	'philemon':        'PHM',
	'phlm':            'PHM',
	'jas':             'JAS',
	'james':           'JAS',
	'jude':            'JUD',
	'rev':             'REV',
	'revelation':      'REV',
}
