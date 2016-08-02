from django.utils.html import escapejs

from pipeline.compilers import CompilerBase


class AngularTemplateCompiler(CompilerBase):
	output_extension = 'js'

	def match_file(self, filename):
		return filename.endswith(('html',))

	def compile_file(self, content, path, force=False, outdated=False):
		if not outdated and not force:
	  		return
	  	return '''
	  		(function() {
		  		angular.module('serverTemplates').run(['$templateCache', function($templateCache) {
					$templateCache.put("{path}", "{content}")
		  		}]);
		  	})();
		'''
	  	# '''.format(path=path, content=escapejs(content))
