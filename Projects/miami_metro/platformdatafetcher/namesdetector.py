# encoding: utf-8
from debra.models import *
import nltk
from social_discovery.blog_discovery import queryset_iterator
import io
import datetime
import string

import re
import unicodedata

# INITIAL DATA: LISTS, DICTS

dividers = [u'+++', u'--', u'::', u':', u'\\', u'/', u'•',
              u'\'', u'-', u'–', u'||', u'|', ]

delimiters = dividers + [u'_', u'@', u'&', u' and ']

re_delimiters = ['\|\|', '\|', '\+\+\+', '\-\-', '\:\:', '\:', '//', '/', '\-', '\–', '•']

stopwords = [u'the', u'is',
             u'.com', u'activities', u'activity', u'addict', u'addiction', u'addicts', u'adventure', u'adventures',
             u'affair', u'afro', u'agency', u'agent', u'agents', u'alert', u'apartment', u'artist', u'artsy', u'avenue',
             u'bake', u'bakes', u'baking', u'bargain', u'bargains', u'beach', u'beaches', u'beard', u'beauty',
             u'bedroom', u'belief', u'believe', u'bella', u'beyond', u'bliss', u'blissful', u'blissfully', u'blog',
             u'blogger', u'blogs', u'blond', u'blonde', u'blush', u'blushes', u'blushing', u'boudoir', u'boulevard',
             u'boutique', u'boy', u'breakfast', u'breakfasts', u'broadcast', u'budget', u'business', u'by', u'cafe',
             u'cake', u'cakes', u'candy', u'care', u'casual', u'cat', u'catalog', u'catalogue', u'cats', u'celeb',
             u'cents', u'champagne', u'charm', u'charmed', u'charming', u'charms', u'chef', u'chic', u'children',
             u'chronicle', u'chronicles', u'cities', u'city', u'classy', u'closet', u'cluster', u'clusters', u'clutch',
             u'co.', u'coast', u'coastal', u'coffee', u'collect', u'collection', u'college', u'confetti', u'conscious',
             u'cook', u'cooking', u'cooks', u'cosmetic', u'cosmetics', u'cosmo', u'country', u'county', u'coupon',
             u'coupons', u'couture', u'craft', u'crafts', u'crafty', u'creation', u'creations', u'crush', u'crushes',
             u'crushing', u'cupcake', u'cupcakes', u'curls', u'cute', u'daily', u'dance', u'dancer', u'dances',
             u'dapper', u'dapperly', u'dash', u'decor', u'decorate', u'decoration', u'delight', u'delights', u'delux',
             u'denim', u'department', u'departments', u'design', u'designer', u'diaries', u'diary', u'dinner',
             u'dinners', u'does', u'dog', u'dogs', u'dollars', u'dream', u'dreamer', u'dreaming', u'dreams', u'dress',
             u'dressy', u'drink', u'drinks', u'early', u'east', u'eastern', u'eat', u'eatery', u'eats', u'evening',
             u'everything', u'experience', u'experiences', u'fab', u'fabulous', u'face', u'factor', u'factors',
             u'family', u'famous', u'fancy', u'fashion', u'feel', u'finger', u'fit', u'fitness', u'flash', u'floral',
             u'florals', u'food', u'foodie', u'foodies', u'foods', u'for', u'fresh', u'friendly', u'frilly', u'from',
             u'frugal', u'fruit', u'fruity', u'fun', u'geek', u'gentleman', u'gentlemans', u'gentlemen', u'gentlemens',
             u'get', u'giggle', u'giggles', u'girl', u'girl', u'girls', u'girls', u'girly', u'glam', u'glamour',
             u'glamourous', u'glass', u'glasses', u'glitter', u'glitters', u'global', u'globe', u'gloss', u'glove',
             u'gloves', u'golden', u'grocery', u'group', u'guide', u'hair', u'handmade', u'handsome', u'happy',
             u'health', u'healthy', u'heart', u'hearts', u'heels', u'hip', u'hipster', u'holiday', u'home',
             u'homemaker', u'hooligan', u'hooligans', u'house', u'how', u'hunter', u'hunters', u'i', u'am', u'in',
             u'jeans', u'journal', u'journals', u'journey', u'kids', u'kill', u'killing', u'kitchen', u'lacquer',
             u'ladies', u'lady', u'late', u'latest', u'life', u'lifestyle', u'lifestyles', u'like', u'live', u'lives',
             u'look', u'lookbook', u'lookbooks', u'looked', u'looks', u'love', u'lovely', u'loves', u'loving', u'lunch',
             u'lunches', u'luxe', u'luxurious', u'luxury', u'madame', u'magazine', u'magpie', u'maker', u'makeup',
             u'mama', u'man', u'manliness', u'manly', u'marks', u'meal', u'meals', u'media', u'men', u'mens',
             u'midtown', u'milk', u'minimal', u'minimalist', u'minimalistic', u'minimally', u'miss', u'mode', u'model',
             u'models', u'modern', u'mom', u'morning', u'mother', u'motherhood', u'mum', u'my', u'nailart', u'nails',
             u'naked', u'native', u'natural', u'neutral', u'new', u'news', u'night', u'northern', u'not', u'nourish',
             u'now', u'nut', u'nuts', u'office', u'oh', u'one', u'online', u'ootd', u'orange', u'organic', u'our',
             u'pacific', u'pants', u'parent', u'parenting', u'parents', u'parties', u'party', u'pearls', u'pennies',
             u'pet', u'petite', u'pets', u'photo', u'photography', u'pilates', u'pink', u'place', u'plant', u'plant',
             u'plant', u'plate', u'play', u'plus', u'polish', u'polished', u'pop', u'positive', u'positively',
             u'preppy', u'pretty', u'princess', u'professional', u'project', u'projects', u'public', u'purple',
             u'purse', u'real', u'relation', u'relations', u'relax', u'reporter', u'review', u'reviews', u'room',
             u'rooms', u'runner', u'runners', u'running', u'rustic', u'salon', u'school', u'scoop', u'scoops',
             u'scrapbook', u'secret', u'secrets', u'sew', u'sewing', u'shoes', u'shop', u'shopper', u'shot', u'simple',
             u'simply', u'sincerely', u'size', u'skin', u'skin', u'skinny', u'skirt', u'smart', u'smarty', u'soccer',
             u'south', u'southern', u'space', u'spaces', u'sparkle', u'sparkles', u'spot', u'stash', u'stitch',
             u'stitches', u'store', u'stories', u'story', u'street', u'studio', u'style', u'style', u'styles',
             u'sustain', u'sustainable', u'swatch', u'tag', u'tale', u'tall', u'target', u'taste', u'tastes', u'tech',
             u'that', u'thing', u'things', u'time', u'time', u'tomboy', u'town', u'travel', u'traveler', u'trend',
             u'trends', u'trendy', u'tropic', u'tropical', u'tropics', u'tutorial', u'universal', u'universe',
             u'upscale', u'uptown', u'urban', u'valley', u'vegan', u'verge', u'verve', u'video', u'videos', u'vintage',
             u'vintage', u'vixin', u'vogue', u'walk', u'walking', u'wander', u'wanderer', u'wandering', u'wardrobe',
             u'we', u'wears', u'wedding', u'week', u'weekend', u'weekly', u'western', u'what', u'when', u'where',
             u'why', u'wine', u'wiw', u'women', u'wonder', u'wonders', u'wore', u'world', u'write', u'writes', u'year',
             u'years', u'yellow', u'yoga', u'young', u'very', u'really', u'real', u'reality', u'fancy', u'feast',
             u'owner', ]

locations = [u'united', u'states', u'united', u'kingdom', u'california', u'england', u'canada', u'new', u'york',
             u'brazil', u'london', u'spain', u'new', u'york', u'australia', u'germany', u'texas', u'france', u'italy',
             u'los', u'angeles', u'florida', u'ontario', u'poland', u'illinois', u'netherlands', u'philippines',
             u'toronto', u'india', u'georgia', u'pennsylvania', u'north', u'carolina', u'chicago', u'\xeele-de-france',
             u'new', u'south', u'wales', u'indonesia', u'paris', u'massachusetts', u'washington', u'singapore',
             u'sydney', u'ohio', u'british', u'columbia', u'virginia', u'ireland', u'madrid', u'victoria', u'san',
             u'francisco', u'community', u'of', u'madrid', u'utah', u'district', u'of', u'columbia', u'washington',
             u'atlanta', u'malaysia', u'melbourne', u'state', u'of', u's\xe3o', u'paulo', u'new', u'jersey', u'arizona',
             u'portugal', u'michigan', u'scotland', u'tennessee', u's\xe3o', u'paulo', u'belgium', u'boston',
             u'colorado', u'vancouver', u'catalonia', u'finland', u'metro', u'manila', u'missouri', u'oregon',
             u'turkey', u'seattle', u'minnesota', u'south', u'africa', u'san', u'diego', u'dallas', u'maryland',
             u'houston', u'sweden', u'russia', u'new', u'zealand', u'manchester', u'barcelona', u'state', u'of', u'rio',
             u'de', u'janeiro', u'south', u'carolina', u'denmark', u'miami', u'mexico', u'queensland', u'indiana',
             u'austin', u'jakarta', u'greece', u'alberta', u'austria', u'berlin', u'rio', u'de', u'janeiro', u'berlin',
             u'manila', u'philadelphia', u'north', u'holland', u'portland', u'lombardy', u'alabama', u'wisconsin',
             u'amsterdam', u'andalusia', u'bavaria', u'united', u'arab', u'emirates', u'milan', u'switzerland',
             u'romania', u'montreal', u'maharashtra', u'argentina', u'north', u'rhine-westphalia', u'nevada',
             u'birmingham', u'kentucky', u'special', u'capital', u'region', u'of', u'jakarta', u'dublin', u'dublin',
             u'japan', u'nashville', u'connecticut', u'the', u'netherlands', u'wales', u'oklahoma', u'dubai', u'hong',
             u'kong', u'lazio', u'valencian', u'community', u'mumbai', u'dubai', u'louisiana', u's\xe3o', u'paulo',
             u'western', u'australia', u'charlotte', u'rome', u'czech', u'republic', u'brisbane', u'denver',
             u'minneapolis', u'phoenix', u'nigeria', u'las', u'vegas', u'western', u'cape', u'hamburg', u'hamburg',
             u'munich', u'pittsburgh', u'delhi', u'new', u'delhi', u'kuala', u'lumpur', u'qu\xe9bec', u'norway',
             u'iowa', u'orlando', u'perth', u'cape', u'town', u'federal', u'territory', u'of', u'kuala', u'lumpur',
             u'salt', u'lake', u'city', u'masovian', u'voivodeship', u'arkansas', u'galicia', u'vienna', u'athens',
             u'moscow', u'moscow', u'hawaii', u'istanbul', u'vienna', u'flanders', u'glasgow', u'republic', u'of',
             u'indonesia', u'kansas', u'valencia', u'leeds', u'calgary', u'istanbul', u'colombia', u'quebec',
             u'brighton', u'oklahoma', u'city', u'baden-w\xfcrttemberg', u'attica', u'lisbon', u'thailand', u'idaho',
             u'warsaw', u'capital', u'region', u'of', u'denmark', u'lisbon', u'auckland', u'auckland', u'saint',
             u'louis', u'singapore', u'kansas', u'city', u'columbus', u'bristol', u'venezuela', u'nebraska', u'chile',
             u'state', u'of', u'minas', u'gerais']

# top 1000 female names
girl_names = [u'heidi', u'toni', u'kristina', u'cora', u'sheryl', u'faye', u'celia', u'latoya', u'leslie', u'janis',
              u'rebecca', u'alison', u'yvette', u'joanna', u'nicole', u'sharon', u'geneva', u'cassandra', u'priscilla',
              u'nina', u'marie', u'frances', u'tasha', u'silvia', u'ella', u'laura', u'maxine', u'karla', u'bridget',
              u'betsy', u'kristen', u'charlene', u'bessie', u'delores', u'patricia', u'linda', u'monique', u'genevieve',
              u'alexandra', u'brooke', u'tiffany', u'jeanette', u'guadalupe', u'jennifer', u'nancy', u'lucia', u'eula',
              u'christine', u'lindsay', u'ashley', u'johnnie', u'naomi', u'carole', u'wilma', u'julia', u'marion',
              u'shelly', u'bethany', u'sadie', u'joanne', u'tricia', u'desiree', u'angelina', u'estelle', u'nadine',
              u'kari', u'brandi', u'stacy', u'amanda', u'alicia', u'suzanne', u'monica', u'annie', u'christy',
              u'deanna', u'della', u'dorothy', u'elena', u'krystal', u'billie', u'patsy', u'hilda', u'sonya', u'jaime',
              u'cindy', u'paulette', u'dianna', u'paula', u'mandy', u'lorene', u'janet', u'catherine', u'marlene',
              u'edith', u'marian', u'kim', u'lauren', u'cathy', u'blanche', u'olga', u'donna', u'joan', u'veronica',
              u'gretchen', u'cecelia', u'alberta', u'gertrude', u'lucy', u'karen', u'elsie', u'beth', u'ernestine',
              u'muriel', u'meredith', u'rita', u'shelia', u'patty', u'michelle', u'loretta', u'megan', u'valerie',
              u'elsa', u'josefina', u'jacquelyn', u'jenna', u'alisha', u'aimee', u'rena', u'myrna', u'samantha',
              u'traci', u'jody', u'krista', u'sonja', u'patti', u'kendra', u'nichole', u'jasmine', u'leticia',
              u'vanessa', u'melissa', u'norma', u'helen', u'madeline', u'amelia', u'jessica', u'jamie', u'barbara',
              u'jackie', u'beatrice', u'angela', u'angelica', u'stacey', u'nettie', u'deborah', u'alyssa', u'jana',
              u'kelley', u'sabrina', u'carolyn', u'erma', u'stephanie', u'agnes', u'vera', u'brenda', u'lynn', u'carla',
              u'rosemary', u'tara', u'eileen', u'isabel', u'marguerite', u'lisa', u'lois', u'esther', u'vicky',
              u'adrienne', u'rosalie', u'kara', u'marianne', u'janie', u'verna', u'darlene', u'bertha', u'dolores',
              u'bernice', u'joyce', u'rhonda', u'carol', u'kristi', u'tonya', u'julie', u'carmen', u'alexis', u'meghan',
              u'vivian', u'stella', u'kelly', u'shannon', u'sonia', u'miriam', u'janice', u'erin', u'geraldine',
              u'marsha', u'betty', u'annette', u'eleanor', u'danielle', u'michele', u'lila', u'terry', u'lena', u'emma',
              u'pauline', u'roxanne', u'gina', u'elizabeth', u'cheryl', u'charlotte', u'marcia', u'ellen', u'carrie',
              u'lora', u'bobbie', u'doreen', u'mona', u'mary', u'jodi', u'elaine', u'marjorie', u'jeannie', u'miranda',
              u'mercedes', u'freda', u'christie', u'raquel', u'kathleen', u'henrietta', u'thelma', u'sandra', u'denise',
              u'kristin', u'melody', u'terri', u'molly', u'angie', u'inez', u'ann', u'jessie', u'natalie', u'robin',
              u'darla', u'shawna', u'elisa', u'ebony', u'melba', u'susie', u'anne', u'francis', u'robyn', u'katherine',
              u'beverly', u'myra', u'theresa', u'margie', u'tammy', u'pamela', u'erica', u'regina', u'laverne', u'tami',
              u'harriet', u'hattie', u'kate', u'katie', u'whitney', u'sara', u'colleen', u'maureen', u'connie',
              u'minnie', u'gwen', u'gladys', u'camille', u'natasha', u'martha', u'marcella', u'yvonne', u'mattie',
              u'vickie', u'ollie', u'tabitha', u'rachael', u'kerry', u'ramona', u'lori', u'sherri', u'jean', u'evelyn',
              u'tamara', u'laurie', u'sarah', u'judy', u'victoria', u'edna', u'tracy', u'marilyn', u'jenny', u'felicia',
              u'doris', u'beulah', u'antoinette', u'renee', u'irene', u'andrea', u'brittany', u'viola', u'courtney',
              u'johanna', u'gayle', u'eunice', u'clara', u'lucille', u'debbie', u'lorraine', u'amber', u'eva', u'mabel',
              u'irma', u'melinda', u'arlene', u'eloise', u'emily', u'amy', u'ethel', u'rosemarie', u'caroline',
              u'belinda', u'margarita', u'josephine', u'sylvia', u'vicki', u'susan', u'christina', u'dianne', u'kelli',
              u'hannah', u'jeanne', u'juana', u'bonnie', u'leona', u'tracey', u'audrey', u'erika', u'katrina',
              u'sheila', u'kellie', u'sophie', u'georgia', u'constance', u'lula', u'lola', u'lynda', u'iris', u'glenda',
              u'lydia', u'maria', u'kristy', u'shelley', u'yolanda', u'anna', u'judith', u'wanda', u'nora', u'wendy',
              u'grace', u'leigh', u'winifred', u'dora', u'rachel', u'cecilia', u'velma', u'becky', u'marta', u'louise',
              u'teri', u'cristina', u'joann', u'nellie', u'dana', u'lillian', u'teresa', u'chelsea', u'mable',
              u'roberta', u'elvira', u'casey', u'delia', u'hazel', u'essie', u'mindy', u'melanie', u'peggy', u'diana',
              u'mamie', u'kimberly', u'claire', u'lindsey', u'maggie', u'kayla', u'mildred', u'lynette', u'tina',
              u'jacqueline', u'rochelle', u'sophia', u'marla', u'latasha', u'tammie', u'jeannette', u'olivia', u'sheri',
              u'willie', u'dawn', u'phyllis', u'jill', u'lorena', u'kristine', u'fannie', u'candace', u'maryann',
              u'bernadette', u'margaret', u'anita', u'antonia', u'lynne', u'kristie', u'marina', u'lillie', u'claudia',
              u'shari', u'allison', u'gwendolyn', u'kathy', u'jane', u'shirley', u'cynthia', u'debra', u'sally',
              u'diane', u'ruth', u'kathryn', u'lela', u'candice', u'gloria', u'tanya', u'heather', u'alice', u'juanita',
              u'gail', u'jennie', u'patrice', u'ronda', u'sherrie', u'addie', u'francine', u'deloris', u'stacie',
              u'adriana', u'cheri', u'shelby', u'abigail', u'celeste', u'cara', u'adele', u'rebekah', u'lucinda',
              u'dorthy', u'chris', u'effie', u'trina', u'reba', u'shawn', u'sallie', u'lenora', u'etta', u'lottie',
              u'kerri', u'trisha', u'nikki', u'estella', u'francisca', u'josie', u'tracie', u'marissa', u'karin',
              u'brittney', u'janelle', u'lourdes', u'laurel', u'helene', u'fern', u'elva', u'corinne', u'kelsey',
              u'bettie', u'elisabeth', u'aida', u'caitlin', u'ingrid', u'eugenia', u'christa', u'goldie', u'cassie',
              u'maude', u'jenifer', u'therese', u'frankie', u'dena', u'lorna', u'janette', u'latonya', u'morgan',
              u'consuelo', u'tamika', u'debora', u'cherie', u'polly', u'dina', u'jewell', u'jillian', u'dorothea',
              u'nell', u'trudy', u'esperanza', u'patrica', u'kimberley', u'shanna', u'helena', u'carolina', u'cleo',
              u'stefanie', u'rosario', u'ola', u'janine', u'mollie', u'lupe', u'alisa', u'lou', u'maribel', u'susanne',
              u'bette', u'susana', u'elise', u'cecile', u'isabelle', u'lesley', u'jocelyn', u'paige', u'joni',
              u'rachelle', u'leola', u'daphne', u'alta', u'ester', u'petra', u'graciela', u'imogene', u'jolene',
              u'keisha', u'lacey', u'glenna', u'gabriela', u'keri', u'ursula', u'lizzie', u'kirsten', u'shana',
              u'adeline', u'mayra', u'jayne', u'jaclyn', u'gracie', u'sondra', u'carmela', u'marisa', u'rosalind',
              u'charity', u'tonia', u'beatriz', u'marisol', u'clarice', u'jeanine', u'sheena', u'angeline', u'frieda',
              u'lily', u'robbie', u'shauna', u'millie', u'claudette', u'cathleen', u'angelia', u'gabrielle',
              u'katharine', u'jodie', u'staci', u'christi', u'jimmie', u'justine', u'elma', u'luella', u'margret',
              u'dominique', u'socorro', u'rene', u'martina', u'margo', u'mavis', u'callie', u'bobbi', u'maritza',
              u'lucile', u'leanne', u'jeannine', u'deana', u'aileen', u'lorie', u'ladonna', u'willa', u'manuela',
              u'gale', u'selma', u'dolly', u'sybil', u'abby', u'lara', u'dale', u'winnie', u'marcy', u'luisa', u'jeri',
              u'magdalena', u'ofelia', u'meagan', u'audra', u'matilda', u'leila', u'cornelia', u'bianca', u'simone',
              u'bettye', u'randi', u'virgie', u'latisha', u'barbra', u'georgina', u'eliza', u'leann', u'bridgette',
              u'rhoda', u'haley', u'adela', u'nola', u'bernadine', u'flossie', u'greta', u'ruthie', u'nelda',
              u'minerva', u'lilly', u'terrie', u'letha', u'hilary', u'estela', u'valarie', u'brianna', u'rosalyn',
              u'earline', u'catalina', u'mia', u'clarissa', u'lidia', u'corrine', u'alexandria', u'concepcion',
              u'sharron', u'rae', u'dona', u'ericka', u'jami', u'elnora', u'chandra', u'lenore', u'neva', u'marylou',
              u'melisa', u'tabatha', u'serena', u'avis', u'allie', u'sofia', u'jeanie', u'odessa', u'nannie',
              u'harriett', u'loraine', u'penelope', u'milagros', u'emilia', u'benita', u'allyson', u'ashlee', u'tania',
              u'tommie', u'esmeralda', u'karina', u'pearlie', u'zelma', u'malinda', u'noreen', u'tameka', u'saundra',
              u'hillary', u'amie', u'althea', u'rosalinda', u'jordan', u'lilia', u'alana', u'clare', u'alejandra',
              u'elinor', u'michael', u'lorrie', u'jerri', u'darcy', u'earnestine', u'carmella', u'taylor', u'noemi',
              u'marcie', u'liza', u'annabelle', u'louisa', u'earlene', u'mallory', u'carlene', u'nita', u'selena',
              u'tanisha', u'katy', u'julianne', u'john', u'lakisha', u'edwina', u'maricela', u'margery', u'roslyn',
              u'kathrine', u'nanette', u'charmaine', u'lavonne', u'ilene', u'kris', u'tammi', u'suzette', u'corine',
              u'kaye', u'jerry', u'merle', u'chrystal', u'lina', u'deanne', u'lilian', u'juliana', u'aline', u'luann',
              u'kasey', u'maryanne', u'evangeline', u'colette', u'melva', u'lawanda', u'yesenia', u'nadia', u'madge',
              u'kathie', u'eddie', u'ophelia', u'valeria', u'nona', u'mitzi', u'mari', u'georgette', u'claudine',
              u'fran', u'alissa', u'roseann', u'lakeisha', u'susanna', u'reva', u'deidre', u'chasity', u'sheree',
              u'carly', u'james', u'elvia', u'alyce', u'deirdre', u'gena', u'briana', u'araceli', u'katelyn',
              u'rosanne', u'wendi', u'tessa', u'berta', u'marva', u'imelda', u'marietta', u'marci', u'leonor',
              u'arline', u'sasha', u'madelyn', u'janna', u'juliette', u'deena', u'aurelia', u'josefa', u'augusta',
              u'liliana', u'christian', u'lessie', u'amalia', u'savannah', u'anastasia', u'vilma', u'natalia',
              u'rosella', u'lynnette', u'corina', u'alfreda', u'leanna', u'carey', u'amparo', u'coleen', u'tamra',
              u'aisha', u'wilda', u'karyn', u'maura', u'evangelina', u'rosanna', u'hallie', u'erna', u'enid',
              u'mariana', u'lacy', u'juliet', u'jacklyn', u'freida', u'madeleine', u'mara', u'hester', u'cathryn',
              u'lelia', u'casandra', u'bridgett', u'angelita', u'jannie', u'dionne', u'annmarie', u'katina', u'beryl',
              u'phoebe', u'millicent', u'katheryn', u'diann', u'carissa', u'maryellen', u'liz', u'lauri', u'helga',
              u'gilda', u'adrian', u'rhea', u'marquita', u'hollie', u'tisha', u'tamera', u'angelique', u'francesca',
              u'britney', u'kaitlin', u'lolita', u'florine', u'rowena', u'reyna', u'twila', u'fanny', u'janell',
              u'ines', u'concetta', u'bertie', u'alba', u'brigitte', u'alyson', u'vonda', u'elba', u'noelle',
              u'letitia', u'deann', u'brandie', u'louella', u'leta', u'felecia', u'sharlene', u'lesa', u'beverley',
              u'robert', u'isabella', u'herminia', u'celina', u'nicolette', u'lorilee', u'crystal', u'fiona',]

boy_names = [u'jacob', u'ethan', u'michael', u'jayden', u'william', u'alexander', u'noah', u'daniel', u'aiden',
             u'anthony', u'joshua', u'mason', u'christopher', u'andrew', u'david', u'matthew', u'logan', u'elijah',
             u'james', u'joseph', u'gabriel', u'benjamin', u'ryan', u'samuel', u'jackson', u'john', u'nathan',
             u'jonathan', u'christian', u'liam', u'dylan', u'landon', u'caleb', u'tyler', u'lucas', u'evan', u'gavin',
             u'nicholas', u'isaac', u'brayden', u'luke', u'brandon', u'jack', u'isaiah', u'jordan', u'owen', u'carter',
             u'connor', u'justin', u'jose', u'jeremiah', u'julian', u'robert', u'aaron', u'adrian', u'wyatt', u'kevin',
             u'cameron', u'zachary', u'thomas', u'charles', u'austin', u'eli', u'chase', u'henry', u'sebastian',
             u'jason', u'levi', u'xavier', u'ian', u'colton', u'dominic', u'juan', u'cooper', u'josiah', u'luis',
             u'ayden', u'carson', u'adam', u'nathaniel', u'brody', u'tristan', u'diego', u'parker', u'blake', u'oliver',
             u'cole', u'carlos', u'jaden', u'jesus', u'alex', u'aidan', u'eric', u'hayden', u'bryan', u'jaxon',
             u'brian', u'bentley', u'alejandro', u'sean', u'nolan', u'riley', u'kaden', u'kyle', u'micah', u'vincent',
             u'antonio', u'colin', u'bryce', u'miguel', u'giovanni', u'timothy', u'jake', u'kaleb', u'steven', u'caden',
             u'bryson', u'damian', u'grayson', u'kayden', u'jesse', u'brady', u'ashton', u'richard', u'victor',
             u'patrick', u'marcus', u'preston', u'joel', u'santiago', u'maxwell', u'ryder', u'edward', u'hudson',
             u'asher', u'devin', u'elias', u'jeremy', u'ivan', u'jonah', u'easton', u'jace', u'oscar', u'collin',
             u'peyton', u'leonardo', u'cayden', u'gage', u'eduardo', u'emmanuel', u'grant', u'alan', u'conner', u'cody',
             u'wesley', u'kenneth', u'mark', u'nicolas', u'malachi', u'george', u'seth', u'kaiden', u'trevor', u'jorge',
             u'derek', u'jude', u'braxton', u'jaxson', u'sawyer', u'jaiden', u'omar', u'tanner', u'travis', u'paul',
             u'camden', u'maddox', u'andres', u'cristian', u'rylan', u'josue', u'roman', u'bradley', u'axel',
             u'fernando', u'garrett', u'javier', u'damien', u'peter', u'abraham', u'ricardo', u'francisco', u'lincoln',
             u'erick', u'drake', u'shane', u'cesar', u'stephen', u'jaylen', u'tucker', u'landen', u'braden', u'mario',
             u'edwin', u'avery', u'manuel', u'trenton', u'ezekiel', u'kingston', u'calvin', u'edgar', u'johnathan',
             u'donovan', u'alexis', u'israel', u'mateo', u'silas', u'jeffrey', u'weston', u'raymond', u'hector',
             u'spencer', u'andre', u'brendan', u'griffin', u'lukas', u'maximus', u'harrison', u'andy', u'braylon',
             u'tyson', u'shawn', u'sergio', u'zane', u'emiliano', u'jared', u'ezra', u'charlie', u'keegan', u'chance',
             u'drew', u'troy', u'greyson', u'corbin', u'simon', u'clayton', u'myles', u'xander', u'dante', u'erik',
             u'rafael', u'martin', u'dominick', u'dalton', u'cash', u'skyler', u'theodore', u'marco', u'caiden',
             u'johnny', u'gregory', u'kyler', u'roberto', u'brennan', u'luca', u'emmett', u'kameron', u'declan',
             u'quinn', u'jameson', u'amir', u'bennett', u'colby', u'pedro', u'emanuel', u'malik', u'graham', u'dean',
             u'jasper', u'everett', u'aden', u'dawson', u'angelo', u'reid', u'abel', u'dakota', u'zander', u'paxton',
             u'ruben', u'judah', u'jayce', u'jakob', u'finn', u'elliot', u'frank', u'fabian', u'dillon', u'brock',
             u'derrick', u'emilio', u'joaquin', u'marcos', u'ryker', u'anderson', u'grady', u'devon', u'elliott',
             u'holden', u'amari', u'dallas', u'corey', u'danny', u'lorenzo', u'allen', u'trey', u'leland', u'armando',
             u'rowan', u'taylor', u'cade', u'colt', u'felix', u'adan', u'jayson', u'tristen', u'julius', u'raul',
             u'braydon', u'zayden', u'julio', u'nehemiah', u'darius', u'ronald', u'louis', u'trent', u'keith',
             u'payton', u'enrique', u'randy', u'scott', u'desmond', u'gerardo', u'jett', u'dustin', u'phillip',
             u'beckett', u'romeo', u'kellen', u'cohen', u'pablo', u'ismael', u'jaime', u'brycen', u'larry', u'kellan',
             u'keaton', u'gunner', u'braylen', u'brayan', u'landyn', u'walter', u'jimmy', u'marshall', u'beau', u'saul',
             u'donald', u'esteban', u'karson', u'reed', u'phoenix', u'brenden', u'tony', u'kade', u'jamari', u'jerry',
             u'mitchell', u'colten', u'arthur', u'brett', u'dennis', u'rocco', u'jalen', u'tate', u'chris', u'quentin',
             u'titus', u'casey', u'brooks', u'izaiah', u'mathew', u'philip', u'zackary', u'darren', u'russell', u'gael',
             u'albert', u'braeden', u'dane', u'gustavo', u'kolton', u'cullen', u'rodrigo', u'alberto', u'leon', u'alec',
             u'damon', u'arturo', u'waylon', u'milo', u'davis', u'walker', u'moises', u'kobe', u'curtis', u'matteo',
             u'august', u'mauricio', u'marvin', u'emerson', u'maximilian', u'reece', u'bryant', u'issac', u'yahir',
             u'uriel', u'hugo', u'mohamed', u'enzo', u'karter', u'lance', u'porter', u'maurice', u'leonel',
             u'zachariah', u'ricky', u'johan', u'nikolas', u'dexter', u'jonas', u'justice', u'knox', u'lawrence',
             u'salvador', u'alfredo', u'gideon', u'maximiliano', u'nickolas', u'talon', u'byron', u'orion', u'solomon',
             u'braiden', u'alijah', u'kristopher', u'rhys', u'gary', u'jacoby', u'davion', u'jamarion', u'pierce',
             u'cason', u'noel', u'ramon', u'kason', u'mekhi', u'shaun', u'warren', u'douglas', u'ernesto', u'ibrahim',
             u'armani', u'cyrus', u'quinton', u'isaias', u'reese', u'jaydon', u'ryland', u'terry', u'frederick',
             u'chandler', u'jamison', u'deandre', u'dorian', u'khalil', u'franklin', u'maverick', u'amare', u'muhammad',
             u'ronan', u'eddie', u'moses', u'roger', u'nasir', u'demetrius', u'adriel', u'brodie', u'kelvin', u'morgan',
             u'tobias', u'ahmad', u'keagan', u'trace', u'alvin', u'giovani', u'kendrick', u'malcolm', u'skylar',
             u'conor', u'camron', u'abram', u'jonathon', u'bruce', u'quincy', u'rohan', u'ahmed', u'nathanael',
             u'barrett', u'remington', u'kamari', u'kristian', u'kieran', u'finnegan', u'xzavier', u'chad',
             u'guillermo', u'uriah', u'rodney', u'gunnar', u'micheal', u'ulises', u'bobby', u'aaden', u'kamden',
             u'kane', u'kasen', u'julien', u'ezequiel', u'lucian', u'atticus', u'javon', u'melvin', u'jeffery',
             u'terrance', u'nelson', u'aarav', u'carl', u'malakai', u'jadon', u'triston', u'harley', u'kian', u'alonzo',
             u'cory', u'marc', u'moshe', u'gianni', u'kole', u'dayton', u'jermaine', u'wilson', u'felipe', u'kale',
             u'terrence', u'nico', u'dominik', u'tommy', u'kendall', u'cristopher', u'isiah', u'finley', u'tristin',
             u'cannon', u'mohammed', u'wade', u'kash', u'marlon', u'ariel', u'madden', u'rhett', u'jase', u'layne',
             u'memphis', u'allan', u'jamal', u'nash', u'jessie', u'joey', u'reginald', u'giovanny', u'lawson',
             u'zaiden', u'korbin', u'rashad', u'urijah', u'billy', u'aron', u'brennen', u'branden', u'leonard', u'rene',
             u'kenny', u'tomas', u'willie', u'darian', u'kody', u'brendon', u'aydan', u'alonso', u'blaine', u'arjun',
             u'raiden', u'layton', u'marquis', u'sincere', u'terrell', u'channing', u'chace', u'iker', u'mohammad',
             u'jordyn', u'messiah', u'omari', u'santino', u'sullivan', u'brent', u'raphael', u'deshawn', u'elisha',
             u'harry', u'luciano', u'jefferson', u'jaylin', u'ray', u'yandel', u'aydin', u'craig', u'tristian',
             u'zechariah', u'bently', u'francis', u'toby', u'tripp', u'kylan', u'semaj', u'alessandro', u'alexzander',
             u'ronnie', u'gerald', u'dwayne', u'jadiel', u'javion', u'markus', u'kolby', u'neil', u'stanley', u'makai',
             u'davin', u'teagan', u'cale', u'harper', u'callen', u'kaeden', u'clark', u'jamie', u'damarion', u'davian',
             u'deacon', u'jairo', u'kareem', u'damion', u'jamir', u'aidyn', u'lamar', u'duncan', u'matias', u'jaeden',
             u'jasiah', u'jorden', u'vicente', u'aryan', u'tyrone', u'yusuf', u'gavyn', u'lewis', u'rogelio', u'zayne',
             u'giancarlo', u'osvaldo', u'rolando', u'camren', u'luka', u'rylee', u'cedric', u'jensen', u'soren',
             u'darwin', u'draven', u'maxim', u'ellis', u'nikolai', u'bradyn', u'mathias', u'zackery', u'zavier',
             u'emery', u'brantley', u'rudy', u'trevon', u'alfonso', u'beckham', u'darrell', u'harold', u'jerome',
             u'daxton', u'royce', u'jaylon', u'rory', u'rodolfo', u'tatum', u'bruno', u'sterling', u'hamza', u'ayaan',
             u'rayan', u'zachery', u'keenan', u'jagger', u'heath', u'jovani', u'killian', u'junior', u'misael',
             u'roland', u'ramiro', u'vance', u'alvaro', u'bode', u'conrad', u'eugene', u'augustus', u'carmelo',
             u'adrien', u'kamron', u'gilberto', u'johnathon', u'kolten', u'wayne', u'zain', u'quintin', u'steve',
             u'tyrell', u'niko', u'antoine', u'hassan', u'jean', u'coleman', u'elian', u'frankie', u'valentin',
             u'adonis', u'jamar', u'jaxton', u'kymani', u'bronson', u'freddy', u'jeramiah', u'kayson', u'hank',
             u'abdiel', u'efrain', u'leandro', u'yosef', u'aditya', u'konnor', u'sage', u'samir', u'todd', u'deven',
             u'derick', u'jovanni', u'demarcus', u'ishaan', u'konner', u'kyson', u'deangelo', u'matthias', u'maximo',
             u'benson', u'dilan', u'gilbert', u'kyron', u'xavi', u'sylas', u'fisher', u'marcel', u'franco', u'jaron',
             u'alden', u'agustin', u'bentlee', u'malaki', u'westin', u'cael', u'jerimiah', u'randall', u'branson',
             u'brogan', u'callum', u'dominique', u'justus', u'krish', u'marcelo', u'ronin', u'odin', u'camryn', u'jair',
             u'izayah', u'brice', u'jabari', u'mayson', u'isai', u'tyree', u'mike', u'samson', u'stefan', u'devan',
             u'emmitt', u'fletcher', u'jaidyn', u'remy', u'casen', u'seamus', u'jedidiah', u'vincenzo', u'gaige',
             u'winston', u'aedan', u'deon', u'jaycob', u'kamryn', u'quinten', u'darnell', u'jaxen', u'deegan',
             u'landry', u'humberto', u'jadyn', u'salvatore', u'aarush', u'edison', u'kadyn', u'abdullah', u'alfred',
             u'ameer', u'carsen', u'jaydin', u'lionel', u'howard', u'davon', u'eden', u'trystan', u'zaire', u'johann',
             u'antwan', u'bodhi', u'jayvion', u'marley', u'theo', u'bridger', u'donte', u'lennon', u'irvin', u'yael',
             u'jencarlos', u'arnav', u'devyn', u'ernest', u'ignacio', u'leighton', u'leonidas', u'octavio', u'rayden',
             u'hezekiah', u'ross', u'hayes', u'lennox', u'nigel', u'vaughn', u'anders', u'keon', u'dario', u'leroy',
             u'cortez', u'darryl', u'jakobe', u'koen', u'darien', u'haiden', u'legend', u'tyrese', u'zaid', u'dangelo',
             u'maxx', u'pierre', u'camdyn', u'chaim', u'damari', u'sonny', u'antony', u'blaise', u'cain', u'pranav',
             u'roderick', u'yadiel', u'eliot', u'broderick', u'lathan', u'makhi', u'ronaldo', u'ralph', u'zack',
             u'kael', u'keyon', u'kingsley', u'talan', u'yair', u'demarion', u'gibson', u'reagan', u'cristofer',
             u'daylen', u'jordon', u'dashawn', u'masen', u'clarence', u'dillan', u'kadin', u'rowen', u'thaddeus',
             u'yousef', u'sheldon', u'slade', u'joziah', u'keshawn', u'menachem', u'bailey', u'camilo', u'destin',
             u'jaquan', u'jaydan']

last_names = [u'walters', u'becker', u'frazier', u'benson', u'steele', u'neal', u'mcgee', u'reese', u'hicks', u'patton',
              u'baker', u'chandler', u'daniel', u'zimmerman', u'richardson', u'thompson', u'kennedy', u'vaughn',
              u'bates', u'wade', u'stanley', u'turner', u'collins', u'owen', u'solis', u'morrison', u'gonzalez',
              u'banks', u'garner', u'manning', u'logan', u'richards', u'austin', u'mendez', u'gilbert', u'smith',
              u'johnson', u'quinn', u'baldwin', u'espinoza', u'gill', u'hines', u'ellis', u'perkins', u'vazquez',
              u'jones', u'martinez', u'olsen', u'briggs', u'kramer', u'evans', u'norris', u'kelly', u'blake',
              u'estrada', u'contreras', u'jacobs', u'barnes', u'hart', u'vega', u'gallagher', u'duran', u'sutton',
              u'holmes', u'lindsey', u'deleon', u'ayala', u'rowe', u'schroeder', u'hampton', u'padilla', u'cunningham',
              u'roberts', u'warren', u'moreno', u'vasquez', u'hamilton', u'knight', u'ward', u'pena', u'rios',
              u'goodman', u'rodriguez', u'barton', u'mejia', u'santiago', u'douglas', u'sandoval', u'griffith',
              u'morrow', u'ford', u'alvarado', u'beck', u'ortega', u'frank', u'parsons', u'jordan', u'cochran',
              u'shepherd', u'torres', u'parker', u'schultz', u'harrison', u'bowman', u'ruiz', u'weaver', u'daniels',
              u'thornton', u'mann', u'mccarthy', u'barnett', u'caldwell', u'moore', u'gomez', u'herrera', u'sparks',
              u'mcguire', u'klein', u'greene', u'burke', u'anderson', u'chapman', u'lawrence', u'garza', u'townsend',
              u'wise', u'floyd', u'griffin', u'burgess', u'francis', u'lopez', u'riley', u'mills', u'meyer', u'cain',
              u'burnett', u'mullins', u'maldonado', u'fleming', u'yates', u'petersen', u'mckenzie', u'serrano',
              u'wilcox', u'castro', u'hoffman', u'cannon', u'miranda', u'sherman', u'drake', u'ballard', u'wang',
              u'tate', u'saunders', u'campos', u'fisher', u'willis', u'matthews', u'sanchez', u'patterson', u'thomas',
              u'marquez', u'reeves', u'robinson', u'robertson', u'webster', u'williams', u'fuller', u'arnold', u'allen',
              u'chang', u'munoz', u'nicholson', u'underwood', u'lewis', u'norton', u'flynn', u'hogan', u'delgado',
              u'terry', u'phillips', u'molina', u'cabrera', u'carter', u'bishop', u'carr', u'wright', u'payne',
              u'wheeler', u'carlson', u'larson', u'harper', u'bowen', u'wolfe', u'hale', u'wilson', u'henderson',
              u'ramos', u'snyder', u'armstrong', u'brady', u'hodges', u'juarez', u'goodwin', u'walton', u'robbins',
              u'mclaughlin', u'nichols', u'ferguson', u'casey', u'spencer', u'peters', u'hanson', u'figueroa',
              u'stewart', u'mason', u'martin', u'warner', u'guzman', u'nguyen', u'stevens', u'murray', u'marsh',
              u'mcbride', u'clarke', u'hudson', u'carroll', u'davidson', u'diaz', u'mendoza', u'leonard', u'lowe',
              u'cox', u'luna', u'ryan', u'fernandez', u'pearson', u'taylor', u'hansen', u'stone', u'boyd', u'schmidt',
              u'chavez', u'aguirre', u'morton', u'wong', u'valdez', u'crawford', u'simpson', u'todd', u'obrien',
              u'brown', u'reed', u'henry', u'soto', u'washington', u'burns', u'waters', u'shelton', u'gregory',
              u'osborne', u'strickland', u'moran', u'tucker', u'freeman', u'hess', u'cervantes', u'glover', u'mueller',
              u'bowers', u'leon', u'nelson', u'bauer', u'woods', u'hernandez', u'cruz', u'lawson', u'blair', u'george',
              u'haynes', u'mckinney', u'dawson', u'edwards', u'franklin', u'lynch', u'gonzales', u'stokes', u'fuentes',
              u'weiss', u'wilkins', u'hoover', u'dennis', u'jenkins', u'wolf', u'malone', u'bell', u'reyes', u'fischer',
              u'james', u'guerrero', u'hughes', u'ramirez', u'pierce', u'dunn', u'lloyd', u'cummings', u'dominguez',
              u'cardenas', u'graves', u'lyons', u'avila', u'brock', u'silva', u'paul', u'ortiz', u'oliver', u'harvey',
              u'hayes', u'simon', u'chen', u'robles', u'wallace', u'meyers', u'horton', u'campbell', u'ingram',
              u'grant', u'brewer', u'holland', u'lucas', u'carson', u'short', u'mack', u'salinas', u'cohen', u'sanders',
              u'jennings', u'cooper', u'peterson', u'dean', u'aguilar', u'lamb', u'harris', u'watson', u'mcdonald',
              u'bryant', u'gibson', u'morales', u'nunez', u'craig', u'rogers', u'rojas', u'rodgers', u'bradley',
              u'myers', u'powell', u'andrews', u'walsh', u'fowler', u'romero', u'montoya', u'adkins', u'fletcher',
              u'dixon', u'palmer', u'hunter', u'gardner', u'gordon', u'wagner', u'curtis', u'santos', u'jensen',
              u'montgomery', u'gibbs', u'kim', u'king', u'webb', u'maxwell', u'chan', u'schneider', u'holt',
              u'schwartz', u'alvarez', u'wells', u'watkins', u'davis', u'brooks', u'lambert', u'harmon', u'newton',
              u'vargas', u'singh', u'butler', u'chambers', u'powers', u'hawkins', u'parks', u'mcdaniel', u'castillo',
              u'shaffer', u'lara', u'weber', u'garrett', u'fitzgerald', u'doyle', u'joseph', u'erickson', u'reid',
              u'fields', u'miller', u'navarro', u'gross', u'carpenter', u'scott', u'howard', u'perry', u'keller',
              u'owens', u'marshall', u'mccormick', u'holloway', u'newman', u'ross', u'miles', u'rhodes', u'byrd',
              u'ochoa', u'russell', u'buchanan', u'cobb', u'stephens', u'welch', u'elliott', u'graham', u'adams',
              u'rivera', u'hammond', u'carrillo', u'duncan', u'pham', u'lang', u'pratt', u'shaw', u'patrick',
              u'pacheco', u'johnston', u'alexander', u'reynolds', u'moss', u'clark', u'watts', u'barker', u'higgins',
              u'cortez', u'bailey', u'hartman', u'coleman', u'gutierrez', u'conner', u'tyler', u'carey', u'poole',
              u'clayton', u'yang', u'oconnor', u'potter', u'salazar', u'cole', u'simmons', u'medina', u'trujillo',
              u'ramsey', u'barber', u'swanson', u'acosta', u'hubbard', u'garcia', u'porter', u'norman', u'harrington',
              u'christensen', u'williamson', u'summers', u'bryan', u'sims', u'burton', u'roth', u'howell', u'barrett',
              u'bennett', u'foster', u'walker', u'perez', u'mitchell', u'kelley', u'flores', u'jackson', u'sullivan',
              u'velasquez', u'stevenson', u'morgan', u'mccoy', u'murphy', u'morris', u'jimenez', u'patel', u'hopkins',
              u'calderon', u'gallegos', u'greer', u'rivas', u'guerra', u'decker', u'collier', u'whitaker', u'bass',
              u'flowers', u'davenport', u'conley', u'houston', u'huff', u'copeland', u'monroe', u'massey', u'roberson',
              u'combs', u'franco', u'larsen', u'pittman', u'randall', u'skinner', u'wilkinson', u'kirby', u'cameron',
              u'bridges', u'anthony', u'richard', u'kirk', u'bruce', u'singleton', u'mathis', u'bradford', u'boone',
              u'abbott', u'charles', u'allison', u'sweeney', u'atkinson', u'jefferson', u'rosales', u'phelps',
              u'farrell', u'castaneda', u'nash', u'dickerson', u'bond', u'wyatt', u'foley', u'chase', u'gates',
              u'vincent', u'mathews', u'hodge', u'garrison', u'trevino', u'villarreal', u'heath', u'dalton',
              u'valencia', u'callahan', u'hensley', u'atkins', u'huffman', u'roy', u'boyer', u'shields', u'lin',
              u'hancock', u'grimes', u'glenn', u'cline', u'delacruz', u'camacho', u'dillon', u'parrish', u'oneill',
              u'melton', u'booth', u'kane', u'berg', u'harrell', u'pitts', u'savage', u'wiggins', u'brennan', u'salas',
              u'marks', u'russo', u'sawyer', u'baxter', u'golden', u'hutchinson', u'liu', u'walter', u'mcdowell',
              u'wiley', u'humphrey', u'johns', u'koch', u'suarez', u'hobbs', u'gilmore', u'ibarra', u'keith', u'macias',
              u'khan', u'andrade', u'stephenson', u'henson', u'wilkerson', u'dyer', u'mcclure', u'blackwell',
              u'mercado', u'tanner', u'eaton', u'barron', u'beasley', u'oneal', u'small', u'preston', u'wu', u'zamora',
              u'macdonald', u'vance', u'mcclain', u'stafford', u'orozco', u'barry', u'shannon', u'kline', u'jacobson',
              u'woodard', u'huang', u'kemp', u'mosley', u'merritt', u'hurst', u'villanueva', u'roach', u'nolan', u'lam',
              u'yoder', u'mccullough', u'lester', u'santana', u'valenzuela', u'winters', u'barrera', u'orr', u'leach',
              u'berger', u'mckee', u'conway', u'stein', u'whitehead', u'bullock', u'escobar', u'knox', u'meadows',
              u'solomon', u'velez', u'odonnell', u'kerr', u'stout', u'blankenship', u'browning', u'kent', u'lozano',
              u'bartlett', u'pruitt', u'barr', u'gaines', u'durham', u'gentry', u'mcintyre', u'sloan', u'rocha',
              u'melendez', u'herman', u'sexton', u'hendricks', u'rangel', u'lowery', u'hardin', u'hull', u'sellers',
              u'ellison', u'calhoun', u'gillespie', u'mora', u'knapp', u'mccall', u'morse', u'dorsey', u'nielsen',
              u'livingston', u'leblanc', u'mclean', u'bradshaw', u'middleton', u'buckley', u'schaefer', u'howe',
              u'house', u'mcintosh', u'pennington', u'reilly', u'hebert', u'mcfarland', u'hickman', u'spears',
              u'conrad', u'arias', u'galvan', u'velazquez', u'huynh', u'frederick', u'randolph', u'cantu',
              u'fitzpatrick', u'mahoney', u'peck', u'villa', u'michael', u'donovan', u'mcconnell', u'walls', u'boyle',
              u'mayer', u'zuniga', u'giles', u'pineda', u'hurley', u'mays', u'mcmillan', u'crosby', u'ayers',
              u'bentley', u'shepard', u'everett', u'pugh', u'mcmahon', u'dunlap', u'bender', u'hahn', u'harding',
              u'acevedo', u'raymond', u'blackburn', u'duffy', u'dougherty', u'bautista', u'shah', u'potts', u'arroyo',
              u'valentine', u'meza', u'gould', u'vaughan', u'avery', u'herring', u'dodson', u'clements', u'sampson',
              u'tapia', u'lynn', u'crane', u'farley', u'cisneros', u'benton', u'mckay', u'finley', u'blevins',
              u'friedman', u'moses', u'sosa', u'blanchard', u'huber', u'frye', u'krueger', u'bernard', u'rosario',
              u'rubio', u'mullen', u'benjamin', u'haley', u'chung', u'moyer', u'choi', u'horne', u'woodward', u'nixon',
              u'hayden', u'rivers', u'estes', u'mccarty', u'richmond', u'stuart', u'maynard', u'brandt', u'oconnell',
              u'hanna', u'sanford', u'sheppard', u'burch', u'levy', u'rasmussen', u'coffey', u'ponce', u'faulkner',
              u'donaldson', u'schmitt', u'novak', u'costa', u'montes', u'booker', u'cordova', u'waller', u'arellano',
              u'maddox', u'mata', u'bonilla', u'stanton', u'compton', u'kaufman', u'dudley', u'mcpherson', u'beltran',
              u'dickson', u'mccann', u'villegas', u'proctor', u'hester', u'cantrell', u'daugherty', u'bray', u'davila',
              u'rowland', u'madden', u'levine', u'spence', u'irwin', u'werner', u'krause', u'petty', u'whitney',
              u'baird', u'hooper', u'pollard', u'zavala', u'jarvis', u'holden', u'hendrix', u'haas', u'mcgrath',
              u'lucero', u'terrell', u'riggs', u'joyce', u'rollins', u'mercer', u'galloway', u'odom', u'andersen',
              u'downs', u'hatfield', u'benitez', u'archer', u'huerta', u'travis', u'mcneil', u'hinton', u'zhang',
              u'hays', u'mayo', u'fritz', u'mooney', u'ewing', u'ritter', u'esparza', u'frey', u'braun', u'riddle',
              u'haney', u'kaiser', u'holder', u'chaney', u'mcknight', u'vang', u'cooley', u'carney', u'cowan',
              u'forbes', u'ferrell', u'davies', u'barajas', u'osborn', u'bright', u'cuevas', u'bolton', u'murillo',
              u'lutz', u'duarte', u'kidd', u'cooke']

# INITIAL DATA END


# HELPER ATOMIC FUNCTIONS

def extract_entities(text):
    for sent in nltk.sent_tokenize(text):
        for chunk in nltk.ne_chunk(nltk.pos_tag(nltk.word_tokenize(sent))):
            if hasattr(chunk, 'label'):
                print chunk.label(), ' '.join(c[0] for c in chunk.leaves())


def extract_names(text):
    results = []
    for sent in nltk.sent_tokenize(text):
        for chunk in nltk.ne_chunk(nltk.pos_tag(nltk.word_tokenize(sent))):
            if hasattr(chunk, 'label') and chunk.label() == 'PERSON':
                if hasattr(chunk, 'leaves') and len(chunk.leaves()) > 0:
                    results.append(' '.join(c[0] for c in chunk.leaves()))
    return results


def compress_spaced(text=u''):
    # compressing single letters together, as for 'J a s m i n e' ==> 'Jasmine'
    compressed = u''
    for p in range(0, len(text)):
        if text[p] == u' ':
            if (p == 0 or text[p-1].isalnum()) and \
                    (p <= 1 or text[p-2] == u' ') and \
                    (p >= (len(text) - 1) or text[p+1].isalnum()) and \
                    (p >= (len(text) - 2) or text[p+2] == u' '):

                pass
            else:
                compressed += text[p]
        else:
            compressed += text[p]
    return u' '.join(compressed.split())


blingies_pattern = re.compile(r'[^\w\s_!"#\$%&\'\(\)\*\+,\-\./:;<=>\?@\[\]\^_`\{\|\}~]+', re.UNICODE)
def strip_blingies(string):
    """
    Strips all that unicode 'fat'
    :param string:
    :return:
    """
    return u' '.join(blingies_pattern.sub(' ', string).split())


punctuation_pattern = re.compile(r'[%s]' % re.escape(string.punctuation))
def check_dict_names(text=u''):
    """
    check for common names from dict and return them if found
    :return:
    """
    stripped_text = text.lower().replace(u"'s", u" ")
    stripped_text = punctuation_pattern.sub(' ', stripped_text)

    stripped_text_words = stripped_text.split()

    found_names = []
    for name in girl_names + boy_names:
        if any([w == name for w in stripped_text_words]) and name not in found_names:
            found_names.append(name)
    return [n.capitalize() for n in found_names]


outer_punctuation = list(u'!"#$%&\'()*+,./:;<=>?@[\\]^_`{|}~') + [u' - ',]
def strip_outer_punctuation(text=u''):
    """
    strips punctuation out of words
    :param text:
    :return:
    """
    for s in outer_punctuation:
        text = text.replace(s, u'')
    return text


domain_pattern = re.compile(r'^[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}$', re.UNICODE)
def validate_single_word(word=u''):
    """
    validates the word, returns False if:
    a) it contains numbers -- 'has_digits'
    b) it is a negative keyword -- 'stopword'
    c) is longer than 14 characters -- 'too_long'
    d) comtains domain extension -- 'domain'
    otherwise: 'valid'
    :param word:
    :return:
    """
    if any(char.isdigit() for char in word):
        return 'has_digits'

    if word.lower() in stopwords:
        return 'stopword'

    if word.lower() in locations:
        return 'location'

    if domain_pattern.match(word.lower()):
        return 'domain'

    if len(word) > 14:
        return 'too_long'

    return 'valid'


def tsplit(string, *delimiters):
    """
    splits by several delimiters
    :param string:
    :param delimiters:
    :return:
    """

    pattern = '|'.join(map(re.escape, delimiters))
    return re.split(pattern, string)


def name_result(name, prob, cause, words=0, names=None, stops=None, eh=None):
    return {'name': name,
            'prob': prob,
            'cause': cause,
            'words': words,
            'names': names,
            'stops': stops}

# HELPER ATOMIC FUNCTIONS END


# FULL ALGORITHM FUNCTIONS

class Probability(object):
    NO = 'no'
    YES = 'yes'
    MAYBE = 'maybe'
    NOT_SET = 'not_set'


# def filter_out_names(text=None):
#     """
#     This function receives a string on input and returns a list of names found.
#     Names are detected according to these rules:
#         0) stuff with digits goes away
#         1) if there are some 1-2 word combinations, that could be possible a name:
#             'John Doe'
#         2) if there are some delimiters (|, +++, --, :, ::, other unicode emoticons symbols) - then split by them
#             and check each part separately:
#             'My Best Personal Blog || Michael Duster', 'Andrea Nair -- Parenting'
#         3) if there are some unsuitable words ('The', 'LLC', 'AG'...), skip this one.
#             'The Vector+ Company Blog', but what about 'Jack The Ripper' name example?
#         4) ??? May be we should split these cases with spaces?
#             'ThisIsSomethingWeird', 'YummyMummyClubDotCa',
#             BUT check out u'Alison McFarland'
#         5) stopwords (shop, brand, best, cheap, etc...):
#             'Sally's Shop'
#             On the contrary, we can find 'Sally' from 'Sally's' part?
#         6) Spacing:
#             'C A S I E  S T E W A R T', 'A m a n d a  T h e b e'
#         7) 'And' and &"
#             'ROSE & LEA'
#         8) commas - do something with several comma-separated names:
#             'beth barnes, Trisha Hughes / Eat Your Beets'
#
#         .......
#         ?) PROFIT!!!
#
#     Weird examples:
#     'Food Blogger | Toronto'
#
#
#     :param string:
#     :return:
#     """
#
#     result = []
#
#     # (0) if we have a digit inside - exiting
#     if any(char.isdigit() for char in text):
#         return result
#
#     # (2) split string by delimiters, looking at 1st one
#     chunks = re.split('|'.join(re_delimiters), text)
#     chunks = [c.strip() for c in chunks]
#
#     if len(chunks) > 0:
#         text = chunks[0].strip()
#
#     # (6) compressing spaced words
#     text = compress_spaced(text)
#
#     # (4) splitting connected words like 'YummyMummyClubDotCa'
#     spared = u''
#     for p in range(0, len(text)):
#         if text[p].isupper():
#             # also leaving as is for 'Mc' surname prefix
#             if p > 0 and text[p-1].islower() and not (p > 1 and text[p-2:p-1] == 'Mc'):
#                 spared += u' '
#         spared += text[p]
#     text = spared
#
#     # (1) now checking only if there are 1 or 2 words
#     chunks = text.split()
#     if len(chunks) > 2:
#         return result
#
#     # (3), (5) removing tag words:
#     chunks = [c.lower() for c in chunks]
#     if not any([sw.lower() in chunks for sw in stopwords]):
#         result.append(u' '.join([c.capitalize() for c in chunks]))
#
#     # For now we should have a string with 1 or 2 words that are probably a name
#
#     return result


# def instagram_name_finder(data_string=None):
#     """
#     Implementation of Lauren's Name Extraction Rules from Instagram platform
#     Summary:
#
#      0. Strip off emoticons, compress spaced words, etc... ?
#
#      1. Detect words quantity in there
#
#      2. For SINGLE-word names:
#          NO: 1 word name with digits
#              1 word name longer than 11 characters
#          YES: 1 word with 3-8 characters
#          MAYBE: 1 word with 2 or less characters
#              1 word with 9-11 characters
#
#      3. For DOUBLE-word names:
#          NO: 2 word names with digits
#              2 word names with stop-words
#              2 word names with total 18 or more characters
#          YES: 2 word names with total 4-15 characters
#          MAYBE: anything with & or any od delimiters: ( -, –, |, \, /, • )
#              2 word names with total length 16-17
#
#      4. For TRIPLE-word names:
#          NO: more than 24 characters and NO punctuation or special chars
#          MAYBE: all the rest
#
#
#     :param data_string: string with raw data from instagram
#     :return: the data string and probability it is the name
#     """
#
#     # probability = Probability.NO
#     if data_string is None:
#         return data_string, Probability.NO, 'None_given'
#
#     # stripping different unicode stuff
#     data_string = strip_blingies(data_string)
#
#     data_string = compress_spaced(data_string)
#
#     # getting words count
#     words = [word for word in data_string.split() if len(word) > 0 and word is not None]
#
#     data_string = ' '.join(words)
#
#     # print('Data string: %r' % data_string)
#
#     result = None
#     probability = Probability.NOT_SET
#     cause = None
#
#     if len(words) == 1:
#         # SINGLE word variant
#         # print('SINGLE word variant')
#
#         # check for digits, if found - then NO
#         if any(char.isdigit() for char in data_string):
#             result = data_string
#             probability = Probability.NO
#             cause = '1_has_digit'
#
#         else:
#             # check word's length:
#             if len(data_string) > 11:
#                 result = data_string
#                 probability = Probability.NO
#                 cause = '1_longer_than_11'
#
#             elif 11 >= len(data_string) >= 3:
#                 result = data_string
#                 probability = Probability.YES
#                 cause = '1_between_3_and_11'
#
#             elif len(data_string) <= 2 or 11 >= len(data_string) >= 9:
#                 result = data_string
#                 probability = Probability.MAYBE
#                 cause = '1_shorter_2_bigger_9'
#
#             else:
#                 result = data_string
#                 probability = Probability.MAYBE
#                 cause = '1_weird'
#
#         return result, probability, cause
#
#     elif len(words) == 2:
#         # DOUBLE word variant
#         # print('DOUBLE word variant')
#
#         # check for digits, if found - then NO
#         if any(char.isdigit() for char in data_string):
#             result = data_string
#             probability = Probability.NO
#             cause = '2_has_digit'
#
#         else:
#
#             # checking for stop words
#             lowered_words = [c.lower() for c in words]
#             if any([sw.lower() in lowered_words for sw in stopwords]):
#                 result = data_string
#                 probability = Probability.NO
#                 cause = '2_stop_words'
#
#             # checking for delimiter
#             if probability == Probability.NOT_SET and any([d in data_string for d in delimiters]):
#                 result = data_string
#                 cause = '2_has_delimiter'
#
#             # check word's length:
#             if probability == Probability.NOT_SET:
#                 if len(data_string) > 18:
#                     result = data_string
#                     probability = Probability.NO
#                     cause = '2_longer_than_18'
#
#                 elif 15 >= len(data_string) >= 4:
#                     result = data_string
#                     probability = Probability.YES
#                     cause = '2_between_4_and_15'
#
#                 elif len(data_string) < 4 or 17 >= len(data_string) >= 16:
#                     result = data_string
#                     probability = Probability.MAYBE
#                     cause = '2_shorter_4_or_between_16_and_17'
#
#                 else:
#                     result = data_string
#                     probability = Probability.MAYBE
#                     cause = '2_weird'
#
#         # checking dict
#         if probability in [Probability.MAYBE, Probability.NO, Probability.NOT_SET]:
#             found_names = check_dict_names(data_string)
#             if len(found_names) > 0:
#                 result = u' // '.join(found_names)
#                 probability = Probability.MAYBE
#                 cause = '2_dict_name'
#
#         return result, probability, cause
#
#     elif len(words) == 3:
#         # TRIPLE word variant
#         # print('TRIPLE word variant')
#
#         # check for name in string:
#         found_names = check_dict_names(data_string)
#         if len(found_names) > 0:
#             return u' // '.join(found_names), Probability.MAYBE, '3_dict_name'
#
#         return data_string, Probability.MAYBE, '3_weird'
#
#     else:
#         # weird stuff, not a name
#         # print('MULTI word variant')
#         return data_string, Probability.MAYBE, 'many'

# FULL ALGORITHM FUNCTIONS END


# TEST INVOKERS

def detect_names_for_influencers(influencers=None):
    """
    Currently we will not use NLTK but will figure just the following algorithm:

    :param influencers:
    :return:
    """
    if isinstance(influencers, InfluencersGroup):
        infs = influencers.influencers
    else:
        infs = queryset_iterator(influencers)

    csvfile = io.open('blogger_names__%s.csv' % datetime.datetime.strftime(
        datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
    csvfile.write(
        u'Influencer_id\tBlog_platform.id\tBlog_platform.url\tInstagram url\tInstagram name\tTwitter url\tTwitter name\tBloglovin url\tBloglovin name\tFacebook url\tFacebook name\n'
    )

    ctr = 0

    # for all of 'bloggers' group
    for blogger in infs:

        # fetching all platforms of a type
        platforms = blogger.platform_set.filter(autovalidated=True).exclude(url_not_found=True)

        # discovered 'raw' names data from platforms
        discovered_names = {
            'Instagram': {},
            'Twitter': {},
            'Bloglovin': {},
            'Facebook': {},
        }

        # going up by all platforms
        for platform in platforms:

            # If that is a platform we look into --
            if platform.platform_name in discovered_names.keys():

                # ...And we have something for 'name' here
                if platform.detected_influencer_attributes is not None and 'name' in platform.detected_influencer_attributes:

                    # for now we just output it to spreadsheet
                    discovered_names[platform.platform_name][platform.url] = platform.detected_influencer_attributes['name']

        csvfile.write(u'%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
            blogger.id,
            blogger.blog_platform.id,
            blogger.blog_platform.url,
            ' '.join(discovered_names['Instagram'].keys()),
            ', '.join(discovered_names['Instagram'].values()),
            ' '.join(discovered_names['Twitter'].keys()),
            ', '.join(discovered_names['Twitter'].values()),
            ' '.join(discovered_names['Bloglovin'].keys()),
            ', '.join(discovered_names['Bloglovin'].values()),
            ' '.join(discovered_names['Facebook'].keys()),
            ', '.join(discovered_names['Facebook'].values()),
        ))

        ctr += 1

        if ctr % 100 == 0:
            print('performed %s influencers' % ctr)

    print('Done')

# LAST ONE:
def test_canadians_insta_names():
    bloggers_col = InfluencersGroup.objects.get(name='alpha-canadian-bloggers')

    csvfile = io.open('insta_blogger_names__%s.csv' % datetime.datetime.strftime(
        datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
    csvfile.write(
        u'Influencer_id\tBlog_platform.id\tBlog_platform.url\tInstagram url\tInstagram name before\tInstagram name after\tIs name?\tCause\tWords ctr\tNames ctr\tStopwords ctr\n'
    )

    ctr = 0

    infs = bloggers_col.influencers

    print('Started performing...')

    # for all of 'bloggers' group
    for blogger in infs:

        # fetching all platforms of a type
        platforms = blogger.platform_set.filter(autovalidated=True,
                                                platform_name='Instagram').exclude(url_not_found=True)

        # discovered 'raw' names data from platforms
        # discovered_names = {
        #     'Instagram': {},
        #     'Twitter': {},
        #     'Bloglovin': {},
        #     'Facebook': {},
        # }

        # going up by all platforms
        for platform in platforms:

            name = None
            prob = None
            cause = None

            # we have something for 'name' here
            found_name = None
            if platform.detected_influencer_attributes is not None and 'name' in platform.detected_influencer_attributes:

                # for now we just output it to spreadsheet
                found_name = platform.detected_influencer_attributes.get('name')
                if found_name:

                    if type(found_name) != unicode:
                        found_name = found_name.decode("utf-8")
                    # name, prob, cause = instagram_name_finder_v2(found_name)
                    result = instagram_name_finder_v2(found_name)

                    if result is not None:

                        csvfile.write(u'%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                            blogger.id,
                            blogger.blog_platform.id,
                            blogger.blog_platform.url,
                            platform.url,
                            found_name,
                            result['name'],
                            result['prob'],
                            result['cause'],
                            result['words'],
                            result['names'],
                            result['stops'],
                        ))

        ctr += 1

        if ctr % 100 == 0:
            print('performed %s influencers' % ctr)

# TEST INVOKERS END









def perform_words_with_delimiters(words=u''):
    """
    performs word with delimiters according list of rules:
    https://docs.google.com/spreadsheets/d/18z6I2WN13bfKB7UMChfiXrEggPuLhCnrkfzYZ5uUFs0/edit#gid=2005936786

    :param words:
    :return: name, probability, cause
    """

    # safety & premeditation
    if words is None:
        return None, Probability.NO, 'none'
    words = u' '.join(words.split())

    # performing separately different delimiters
    # the underscore -- '_'
    if u'_' in words:
        phrase_chunks = [w for w in words.split(u'_') if len(w) > 0]
        if len(phrase_chunks) == 1:
            return handle_single_word(u' '.join(phrase_chunks))
        elif len(phrase_chunks) == 2:
            return handle_double_words(u' '.join(phrase_chunks))
        elif len(phrase_chunks) == 3:
            return handle_triple_words(u' '.join(phrase_chunks))
        else:
            return handle_multiple_words(u' '.join(phrase_chunks))

    # the '@' sign
    if u'@' in words:
        payload = words.split(u'@')[0].strip()
        chunks = [w for w in payload.split() if len(w) > 0]
        if len(chunks) == 1:
            return handle_single_word(u' '.join(chunks))
        elif len(chunks) == 2:
            return handle_double_words(u' '.join(chunks))
        elif len(chunks) == 3:
            return handle_triple_words(u' '.join(chunks))
        else:
            return handle_multiple_words(u' '.join(chunks))

    # Apostrophe '\''
    if u'\'' in words:
        # 1st type: 's ending
        chunks = words.split()
        if any([w.lower().endswith(u"'s") for w in chunks]):

            apostrophed_word = None
            apostrophed_word_idx = None
            for i, w in enumerate(chunks):
                if w.lower().endswith(u"'s"):
                    apostrophed_word = w[:-2]
                    apostrophed_word_idx = i
                    break

            # if the word is in names list -- it is the name we seek
            if apostrophed_word.lower() in girl_names + boy_names:
                return apostrophed_word, Probability.YES, 'apostrophed_name'

            # if it is stopword -- it is not a name
            if apostrophed_word.lower() in stopwords + locations:
                return apostrophed_word, Probability.NO, 'apostrophed_stopword'

            # if unknown word apostrophed, checking its predecessor
            if apostrophed_word_idx > 0 and chunks[apostrophed_word_idx-1].lower() in girl_names + boy_names:
                return u'%s %s' % (chunks[apostrophed_word_idx-1], apostrophed_word), \
                       Probability.YES, \
                       'apostrophed_unknown_with_name'

            return apostrophed_word, Probability.MAYBE, 'apostrophed_weird_s'

        # 2nd type: Separate apostrophe will be performed as divider '|'

        # 3rd type: if it is inside of a word --
        # should be checked when calling this function and not call it for this case.

        # 4th type: discard it if it is not surrounded by spaces or letters
        if any([w.lower().endswith(u"'") for w in chunks]):
            new_chunks = []
            for c in chunks:
                if c.endswith(u"'"):
                    new_chunks.append(c[:-1])
                else:
                    new_chunks.append(c)

            if len(new_chunks) == 1:
                return handle_single_word(u' '.join(new_chunks))
            elif len(new_chunks) == 2:
                return handle_double_words(u' '.join(new_chunks))
            elif len(new_chunks) == 3:
                return handle_triple_words(u' '.join(new_chunks))
            else:
                return handle_multiple_words(u' '.join(new_chunks))

    # -'s
    #if it is inside of a word -- should be checked when calling this function and not call it for this case.

    # dividers
    dividers_to_check = [u'|', ]

    if any([d in words for d in dividers_to_check]):
        chunks = words.split()

        # getting indexes of delimiters in words sequence
        dividers_idx = []
        for i, w in enumerate(chunks):
            if w in dividers_to_check:
                dividers_idx.append(i)

    return u'Not_implemented', u'Not_implemented', u'Not_implemented'




def handle_single_word(word=u''):
    """
    Checks if single word is a name.

    1) if there is one word, we check if there is a delimiter in it.
        a) if it is, then split the word and treat it by punctuation rules, if none then as DOUBLE-word, TRIPLE-word, MULTI-word

    2) if no delimiters - validating teh word.
         a) if any reason except 'valid' --> result is 'NO'
    3) if it is ok, checking its length
         a) if <3 or > 11 --> 'MAYBE'
         b) if >3 and <11 --> 'YES'

    :param word:
    :return: name, probability, cause
    """

    # safety & premeditation
    if word is None:
        return name_result(None, Probability.NO, 'none')

    word = word.strip()

    # # check if there are delimiters in it
    # if any([d in word for d in delimiters]):
    #     return perform_words_with_delimiters(word)

    names = 1 if word.lower() in girl_names + boy_names else 0
    stops = 1 if word.lower() in stopwords + locations else 0

    # validating the word
    validation_result = validate_single_word(word)
    if validation_result == 'valid':

        # checking its length
        if 11 >= len(word) >= 3:
            # return word, Probability.YES, '1_%s_from_3_to_11' % validation_result
            return name_result(word,
                               Probability.YES,
                               '1_%s_from_3_to_11' % validation_result,
                               1,
                               names,
                               stops,)
        else:
            # return word, Probability.MAYBE, '1_%s_lower_3_longer_11' % validation_result
            return name_result(word,
                               Probability.MAYBE,
                               '1_%s_lower_3_longer_11' % validation_result,
                               1,
                               names,
                               stops,)

    else:
        # return word, Probability.NO, validation_result
        return name_result(word,
                           Probability.NO,
                           '1_%s' % validation_result,
                           1,
                           names,
                           stops,)


def handle_double_words(words=u''):

    chunks = words.split()
    chunks_analysis = []

    names = 0
    for c in chunks:
        if c.lower() in girl_names + boy_names:
            names += 1

    stops = 0
    for c in chunks:
        if c.lower() in stopwords + locations:
            stops += 1

    for c in chunks:
        v = validate_single_word(c)
        chunks_analysis.append({'word': c, 'type': v})

    if chunks_analysis[0]['type'] == 'valid' and chunks_analysis[1]['type'] == 'valid':
        return name_result(u' '.join(chunks),
                           Probability.YES,
                           'double_both_name',
                           2,
                           names,
                           stops,)

    if chunks_analysis[0]['type'] == 'valid' and chunks_analysis[0]['word'].lower() in boy_names + girl_names:
        return name_result(chunks_analysis[0]['word'],
                           Probability.YES,
                           'double_first_is_name',
                           2,
                           names,
                           stops,)

    if chunks_analysis[1]['type'] == 'valid' and chunks_analysis[1]['word'].lower() in boy_names + girl_names:
        return name_result(chunks_analysis[1]['word'],
                           Probability.YES,
                           'double_second_is_name',
                           2,
                           names,
                           stops,)

    if chunks_analysis[0]['type'] != 'valid' and chunks_analysis[1]['type'] != 'valid':
        return name_result(u'',
                           Probability.NO,
                           'double_invalid',
                           2,
                           names,
                           stops,)

    if chunks_analysis[0]['type'] == 'valid':
        return name_result(chunks_analysis[0]['word'],
                           Probability.MAYBE,
                           'double_maybe_first',
                           2,
                           names,
                           stops,)

    if chunks_analysis[1]['type'] == 'valid':
        return name_result(chunks_analysis[1]['word'],
                           Probability.MAYBE,
                           'double_maybe_second',
                           2,
                           names,
                           stops,)

    return name_result(u' '.join(chunks),
                       Probability.MAYBE,
                       'double_maybe',
                       2,
                       names,
                       stops,)


def handle_triple_words(words=u''):
    """
    If no word in the 3-word name is a name word… And no word is negative… we mark it as a MAYBE.
    If no word is a name word… and there is a negative indicator… we mark the entire thing as a NO.
    If 1 or more words is a name word (and no negative indicators), we mark the entire name as a yes.
    If 1 or more words is a name word and there is one or more negative indicators… we keep ONLY the name word
    and discard any unknown words and any negative words.
    """
    # check for name in string:
    found_names = check_dict_names(words)

    chunks = words.split()

    names = 0
    for c in chunks:
        if c.lower() in girl_names + boy_names:
            names += 1

    stops = 0
    for c in chunks:
        if c.lower() in stopwords + locations:
            stops += 1

    if len(found_names) == 0 and stops == 0:
        return name_result(words,
                           Probability.MAYBE,
                           '3_dict_undecided',
                           3,
                           names,
                           stops)

    if len(found_names) == 0 and stops > 0:
        return name_result(words,
                           Probability.NO,
                           '3_nameless_stopword',
                           3,
                           names,
                           stops)

    if len(found_names) > 0 and stops == 0:
        return name_result(words,
                           Probability.YES,
                           '3_full_name',
                           3,
                           names,
                           stops)

    if len(found_names) > 0 and stops > 0:
        return name_result(u' // '.join(found_names),
                           Probability.YES,
                           '3_partial_name',
                           3,
                           names,
                           stops)

    return name_result(words,
                       Probability.MAYBE,
                       '3_weird',
                       3,
                       names,
                       stops)


def handle_multiple_words(words=u''):
    """
    If no word in the 3-word name is a name word… And no word is negative… we mark it as a MAYBE.
    If no word is a name word… and there is a negative indicator… we mark the entire thing as a NO.
    If 1 or more words is a name word (and no negative indicators), we mark the entire name as a yes.
    If 1 or more words is a name word and there is one or more negative indicators… we keep ONLY the name word
    and discard any unknown words and any negative words.
    """
    # check for name in string:
    found_names = check_dict_names(words)

    chunks = words.split()

    names = 0
    for c in chunks:
        if c.lower() in girl_names + boy_names:
            names += 1

    stops = 0
    for c in chunks:
        if c.lower() in stopwords + locations:
            stops += 1

    has_stopword = any([w.strip().lower() in stopwords + locations for w in words.split()])

    if len(found_names) == 0 and stops == 0:
        return name_result(words,
                           Probability.MAYBE,
                           'multi_dict_undecided',
                           len(chunks),
                           names,
                           stops)

    if len(found_names) == 0 and stops > 0:
        return name_result(words,
                           Probability.NO,
                           'multi_nameless_stopword',
                           len(chunks),
                           names,
                           stops)

    if len(found_names) > 0 and stops == 0:
        return name_result(words,
                           Probability.YES,
                           'multi_full_name',
                           len(chunks),
                           names,
                           stops)

    if len(found_names) > 0 and stops > 0:
        return name_result(u' // '.join(found_names),
                           Probability.YES,
                           'multi_partial_name',
                           len(chunks),
                           names,
                           stops)

    return name_result(words,
                       Probability.MAYBE,
                       'multi_weird',
                       len(chunks),
                       names,
                       stops)


def instagram_name_finder_v2(data_string=None):
    """
    Implementation of Lauren's Name Extraction Rules from Instagram platform
    Summary:

     0. Strip off emoticons, compress spaced words, etc... ?

     1. Detect words quantity in there

     2. For SINGLE-word names:
         NO: 1 word name with digits
             1 word name longer than 11 characters
         YES: 1 word with 3-8 characters
         MAYBE: 1 word with 2 or less characters
             1 word with 9-11 characters

     3. For DOUBLE-word names:
         NO: 2 word names with digits
             2 word names with stop-words
             2 word names with total 18 or more characters
         YES: 2 word names with total 4-15 characters
         MAYBE: anything with & or any od delimiters: ( -, –, |, \, /, • )
             2 word names with total length 16-17

     4. For TRIPLE-word names:
         NO: more than 24 characters and NO punctuation or special chars
         MAYBE: all the rest


    :param data_string: string with raw data from instagram
    :return: the data string and probability it is the name
    """

    # probability = Probability.NO
    if data_string is None:
        # return data_string, Probability.NO, 'None_given'
        return name_result(data_string, Probability.NO, 'None_given')

    # stripping different unicode stuff
    data_string = unicodedata.normalize('NFKC', data_string)

    data_string = compress_spaced(data_string)

    data_string = strip_blingies(data_string)

    # PREPARATION and PRE-PROCESSING
    # perform

    data_string = u' '.join(data_string.split())

    # # TODO: showing only non-punctuation words
    # if any([p in data_string for p in string.punctuation]):
    #     return None

    # performing separately different delimiters

    # Parenthesis / brackets (the most severe)
    if u'(' in data_string and u')' in data_string:
        result = perform_parenthesised(data_string)
        if result['prob'] == Probability.YES or result['prob'] == Probability.MAYBE:
            # return name, prob, cause
            return result

    # the underscore -- '_'
    if u'_' in data_string:
        # simple - just replace with space and perform.
        data_string = data_string.replace(u'_', u' ')

    # the '@' sign
    if u'@' in data_string:
        # simple - taking left part of splitted string by @
        data_string = data_string.split(u'@')[0].strip()

    # Apostrophes
    if u'\'' in data_string:

        # 1st type: 's ending
        chunks = data_string.split()
        if any([w.lower().endswith(u"'s") for w in chunks]):

            names = len([chunk.lower().replace(u'\'s', u'') in girl_names + boy_names for chunk in chunks])
            stops = len([chunk.lower().replace(u'\'s', u'') in stopwords + locations for chunk in chunks])

            apostrophed_word = None
            apostrophed_word_idx = None
            for i, w in enumerate(chunks):
                if w.lower().endswith(u"'s"):
                    apostrophed_word = w[:-2]
                    apostrophed_word_idx = i
                    break

            # if the word is in names list -- it is the name we seek -- FAST RESULT
            if apostrophed_word.lower() in girl_names + boy_names:
                return name_result(apostrophed_word,
                                   Probability.YES,
                                   'apostrophed_name',
                                   len(chunks),
                                   names,
                                   stops,
                                   )
                # return apostrophed_word, Probability.YES, 'apostrophed_name'

            # if it is stopword -- it is not a name -- FAST RESULT
            if apostrophed_word.lower() in stopwords + locations:
                return name_result(apostrophed_word,
                                   Probability.NO,
                                   'apostrophed_stopword',
                                   len(chunks),
                                   names,
                                   stops,
                                   )
                # return apostrophed_word, Probability.NO, 'apostrophed_stopword'

            # if unknown word apostrophed, checking its predecessor -- FAST RESULT
            if apostrophed_word_idx > 0 and chunks[apostrophed_word_idx-1].lower() in girl_names + boy_names:
                return name_result(u'%s %s' % (chunks[apostrophed_word_idx-1], apostrophed_word),
                                   Probability.YES,
                                   'apostrophed_unknown_with_name',
                                   len(chunks),
                                   names,
                                   stops,
                                   )
                # return u'%s %s' % (chunks[apostrophed_word_idx-1], apostrophed_word), \
                #        Probability.YES, \
                #        'apostrophed_unknown_with_name'

        # 2nd type: Separate apostrophe will be performed as divider later

        # 3rd type: if it is inside of a word -- skip it and deal with it as with a single word

        # 4th type: discard it if it is not surrounded by spaces or letters and perform as usual
        # TODO: may be use regex here later?
        rebuilt_data_string = u""
        for i, l in enumerate(data_string):
            if l == u"'":
                if i == 0 or i == len(data_string)-1:
                    continue
                if (data_string[i-1] == u' ' and data_string[i+1] != u' ') or \
                        (data_string[i-1] != u' ' and data_string[i+1] == u' '):
                    continue
            rebuilt_data_string += l
        data_string = rebuilt_data_string

    # -'s
    # if it is inside of a word -- treating it like a letter. otherwise it is a delimiter

    # Dividers.  We will use FAST-RESULT approach here
    dividers_to_check = [u'|', u' - ', u' \' ']

    if any([d in data_string for d in dividers_to_check]):

        # these chunks are pieces of text divided by delimiters
        # chunks = tsplit(data_string, *dividers_to_check)
        #
        # # print(u'Dividers chunks: %s' % chunks)
        #
        # # data to analyze chunks
        # chunks_analysis = []  # [[{'word': 'Amy', 'type': 'name'}, {'word': 'Whoohoo', 'type': 'unknown'}][{'word': 'blogger', 'type': 'stop'}]]
        #
        # # analyzing chunks
        # for chunk in chunks:
        #     sub_chunk = []
        #     for word in chunk.split():
        #         if word.lower().strip() in stopwords + locations:
        #             sub_chunk.append({'word': word, 'type': 'stop'})
        #         elif word.lower().strip() in boy_names + girl_names:
        #             sub_chunk.append({'word': word, 'type': 'name'})
        #         else:
        #             sub_chunk.append({'word': word, 'type': 'unknown'})
        #     chunks_analysis.append(sub_chunk)
        #
        # # print(u'Chunks analysis: %s' % chunks_analysis)
        #
        # resulting_names = []
        # for chunk in chunks_analysis:
        #     found_name = False  # True if previousely we found a name
        #     current_name = []  # capacitor for current name
        #     for word_data in chunk:
        #         if word_data['type'] == 'name' and found_name is False:
        #             found_name = True
        #             current_name.append(word_data['word'])
        #         elif found_name is True:
        #             current_name.append(word_data['word'])
        #             resulting_names.append(u" ".join(current_name))
        #             found_name = False
        #             current_name = []
        #
        #     if len(current_name) > 0:
        #         resulting_names.append(u" ".join(current_name))
        #         current_name = []
        #
        # # print(u'resulting names: %s' % resulting_names)
        #
        # # FAST RESULT
        # if len(resulting_names) > 0:
        #     return u' // '.join(resulting_names), Probability.YES, 'divider_names'

        # if prob == Probability.YES or prob == Probability.MAYBE:
        #     return name, prob, cause

        res = perform_divided(data_string)
        return res

    # & and AND
    if any([d in data_string.lower() for d in [u'&', u' and ']]):
        # ensure that & are spaced
        rebuilt_data_string = u' '.join(data_string.replace(u' and ', u' & ').replace(u'&', u' & ').split())
        chunks = rebuilt_data_string.split()

        # print(u'Chunks: %s' % chunks)

        left_word = chunks[chunks.index(u'&')-1] if chunks.index(u'&')-1 >= 0 else None
        right_word = chunks[chunks.index(u'&')+1] if chunks.index(u'&')+1 < len(chunks) else None

        # print(u'Left word: %r' % left_word)
        # print(u'Right word: %r' % right_word)

        resulting_names = [n for n in [left_word, right_word] if n is not None
                           and n.lower() in boy_names + girl_names
                           and n.lower() not in stopwords + locations]

        # print(u'Resulting names: %r' % resulting_names)

        # FAST RESULT
        if len(resulting_names) > 0:
            return name_result(u' // '.join(resulting_names),
                               Probability.YES,
                               'and_names',
                               len(chunks),
                               len([chunk.lower() in girl_names + boy_names for chunk in chunks]),
                               len([chunk.lower() in stopwords + locations for chunk in chunks]),
                               )
            # return u' // '.join(resulting_names), Probability.YES, 'and_names'
        else:
            return name_result(u'',
                               Probability.NO,
                               'and_no_names',
                               len(chunks),
                               len([chunk.lower() in girl_names + boy_names for chunk in chunks]),
                               len([chunk.lower() in stopwords + locations for chunk in chunks]),
                               )
            # return u'', Probability.NO, 'and_no_names'

    # removing dividers
    rebuilt_data_string = data_string
    for d in dividers:
        rebuilt_data_string = rebuilt_data_string.replace(d, u" ")
    data_string = u" ".join(rebuilt_data_string.split())

    # stripping punctuation
    data_string = strip_outer_punctuation(data_string)

    # getting words count
    words = [word for word in data_string.split() if len(word) > 0 and word is not None]

    data_string = ' '.join(words)

    # print('Data string: %r' % data_string)

    if len(words) == 1:
        # SINGLE word variant
        # print('SINGLE word variant')

        # # check for digits, if found - then NO
        # if any(char.isdigit() for char in data_string):
        #     result = data_string
        #     probability = Probability.NO
        #     cause = '1_has_digit'
        #
        # else:
        #     # check word's length:
        #     if len(data_string) > 11:
        #         result = data_string
        #         probability = Probability.NO
        #         cause = '1_longer_than_11'
        #
        #     elif 11 >= len(data_string) >= 3:
        #         result = data_string
        #         probability = Probability.YES
        #         cause = '1_between_3_and_11'
        #
        #     elif len(data_string) <= 2 or 11 >= len(data_string) >= 9:
        #         result = data_string
        #         probability = Probability.MAYBE
        #         cause = '1_shorter_2_bigger_9'
        #
        #     else:
        #         result = data_string
        #         probability = Probability.MAYBE
        #         cause = '1_weird'

        result = handle_single_word(data_string)
        return result

    elif len(words) == 2:
        # DOUBLE word variant
        # print('DOUBLE word variant')

        # # check for digits, if found - then NO
        # if any(char.isdigit() for char in data_string):
        #     result = data_string
        #     probability = Probability.NO
        #     cause = '2_has_digit'
        #
        # else:
        #
        #     # checking for stop words
        #     lowered_words = [c.lower() for c in words]
        #     if any([sw.lower() in lowered_words for sw in stopwords]):
        #         result = data_string
        #         probability = Probability.NO
        #         cause = '2_stop_words'
        #
        #     # checking for delimiter
        #     if probability == Probability.NOT_SET and any([d in data_string for d in delimiters]):
        #         result = data_string
        #         cause = '2_has_delimiter'
        #
        #     # check word's length:
        #     if probability == Probability.NOT_SET:
        #         if len(data_string) > 18:
        #             result = data_string
        #             probability = Probability.NO
        #             cause = '2_longer_than_18'
        #
        #         elif 15 >= len(data_string) >= 4:
        #             result = data_string
        #             probability = Probability.YES
        #             cause = '2_between_4_and_15'
        #
        #         elif len(data_string) < 4 or 17 >= len(data_string) >= 16:
        #             result = data_string
        #             probability = Probability.MAYBE
        #             cause = '2_shorter_4_or_between_16_and_17'
        #
        #         else:
        #             result = data_string
        #             probability = Probability.MAYBE
        #             cause = '2_weird'
        #
        # # checking dict
        # if probability in [Probability.MAYBE, Probability.NO, Probability.NOT_SET]:
        #     found_names = check_dict_names(data_string)
        #     if len(found_names) > 0:
        #         result = u' // '.join(found_names)
        #         probability = Probability.MAYBE
        #         cause = '2_dict_name'

        result = handle_double_words(data_string)
        return result

    elif len(words) == 3:
        # TRIPLE word variant
        # print('TRIPLE word variant')

        # # check for name in string:
        # found_names = check_dict_names(data_string)
        # if len(found_names) > 0:
        #     return u' // '.join(found_names), Probability.MAYBE, '3_dict_name'
        #
        # return data_string, Probability.MAYBE, '3_weird'

        result = handle_triple_words(data_string)
        return result

    else:
        # weird stuff, not a name
        # print('MULTI word variant')

        result = handle_multiple_words(data_string)
        return result


def perform_parenthesised(data_string=u''):
    """
    This function performs string with parenthesis.
    1) extract text from parenthesis and treat it and remaining as separate texts.
    2) take best result

    :param data_string:
    :return:
    """

    if data_string is None:
        return name_result(data_string, Probability.NO, 'None_given')

    built_data_string = data_string
    text_parts = []
    results = []

    # performing simple parenthesis
    if u'(' in built_data_string and u')' in built_data_string:
        performed = True
        while performed:
            performed = False
            start = built_data_string.find(u'(')
            end = built_data_string.find(u')')

            # found a group
            if start > -1 and end > -1:

                part = built_data_string[start+1:end]
                text_parts.append(part.replace(u'(', u'').replace(u')', u''))
                built_data_string = built_data_string[:start] + built_data_string[end+1:]
                performed = True

        text_parts.append(built_data_string)

        # print(u'Text parts: %s' % text_parts)
        for tp in text_parts:
            result = instagram_name_finder_v2(tp)
            results.append(result)

        # print(u'Results: %s' % results)

        maybe = None
        # returning first successfull match
        for res in results:
            if res['prob'] == Probability.YES:
                # return res
                return name_result(res['name'],
                                   res['prob'],
                                   res['cause'],
                                   u'|'.join([unicode(w['words']) for w in results]),
                                   u'|'.join([unicode(w['names']) for w in results]),
                                   u'|'.join([unicode(w['stops']) for w in results]),)
            elif res['prob'] == Probability.MAYBE and maybe is None:
                maybe = res

        if maybe is None:
            return name_result(data_string,
                               Probability.NO,
                               'parenthesis_nothing_found',
                               u'|'.join([unicode(w['words']) for w in results]),
                               u'|'.join([unicode(w['names']) for w in results]),
                               u'|'.join([unicode(w['stops']) for w in results]),
                               )
        else:
            # return maybe['name'], maybe['prob'], maybe['cause']
            return name_result(maybe['name'],
                               maybe['prob'],
                               maybe['cause'],
                               u'|'.join([unicode(w['words']) for w in results]),
                               u'|'.join([unicode(w['names']) for w in results]),
                               u'|'.join([unicode(w['stops']) for w in results]),
                               )


def perform_divided(data_string=u''):
    """
    This function performs string with parenthesis.
    1) perform splitted stuff as separate texts.
    2) take best result

    :param data_string:
    :return:
    """

    if data_string is None:
        return name_result(data_string, Probability.NO, 'None_given')

    dividers_to_check = [u'|', u' - ', u' \' ']

    chunks = tsplit(data_string, *dividers_to_check)

    results = []

    for chunk in chunks:
        result = instagram_name_finder_v2(chunk)
        results.append(result)

    maybe = None
    # returning first successfull match
    for res in results:
        if res['prob'] == Probability.YES:
            return res
        elif res['prob'] == Probability.MAYBE and maybe is None:
            maybe = res

    if maybe is None:
        # return data_string, Probability.NO, 'dividers_nothing_found'
        return name_result(data_string,
                           Probability.NO,
                           'dividers_nothing_found',
                           u'|'.join([unicode(w['words']) for w in results]),
                           u'|'.join([unicode(w['names']) for w in results]),
                           u'|'.join([unicode(w['stops']) for w in results]),
                           )
    else:
        # return maybe['name'], maybe['prob'], maybe['cause']
        return name_result(maybe['name'],
                           maybe['prob'],
                           maybe['cause'],
                           u'|'.join([unicode(w['words']) for w in results]),
                           u'|'.join([unicode(w['names']) for w in results]),
                           u'|'.join([unicode(w['stops']) for w in results]),
                           )
