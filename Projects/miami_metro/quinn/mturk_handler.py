######## MTurk handling ########
from boto.mturk.connection import MTurkConnection
from boto.mturk.question import QuestionContent,Question,QuestionForm, Overview,AnswerSpecification,SelectionAnswer,FormattedContent,FreeTextAnswer
 
from django.conf import settings


ACCESS_ID = settings.AWS_KEY
SECRET_KEY = settings.AWS_PRIVATE_KEY
HOST = 'mechanicalturk.sandbox.amazonaws.com'
 
mtc = MTurkConnection(aws_access_key_id=ACCESS_ID,
                      aws_secret_access_key=SECRET_KEY,
                      host=HOST)
title = 'Transcription of promotions from image into text'
description = ('Find the promotion information from the image provided.')
keywords = 'image, text, promotion'


#---------------  BUILD OVERVIEW -------------------
 
overview = Overview()
overview.append_field('Title', title)
overview.append(FormattedContent('<a target="_blank"'
                                 ' href="http://google.com">'
                                 ' Hello</a>'))



#---------------  BUILD QUESTION 1 -------------------
 
qc1 = QuestionContent()
qc1.append_field('Title','How looks the design ?')
 
fta1 = SelectionAnswer(min=1, max=1,style='dropdown',
                      selections=ratings,
                      type='text',
                      other=False)
 
q1 = Question(identifier='design',
              content=qc1,
              answer_spec=AnswerSpecification(fta1),
              is_required=True)