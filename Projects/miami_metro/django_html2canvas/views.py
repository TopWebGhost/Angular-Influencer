from django.http import HttpResponse
import urllib2
import base64
import simplejson as json
import urlparse
import pdb

def imgProxy(request):
    print "called"
    response = HttpResponse()
    if request.GET.get('url') != "" and request.GET.get('callback') != "":
        try:
            url = request.GET.get('url');

            urlInfo = urlparse.urlparse(url);

            if urlInfo.scheme in ["http","https"]:
                result = urllib2.urlopen(url)
                requestInfo = result.info();
                if requestInfo['content-type'] in ["image/jpeg","image/png","image/gif"] or "image/png" in requestInfo['content-type'] or "image/jpg" in requestInfo['content-type'] or "image/jpeg" in requestInfo['content-type'] or "image/gif" in requestInfo['content-type'] or "text/html" in requestInfo['content-type'] or "application/xhtml" in requestInfo['content-type'] or "application/octet-stream" in requestInfo['content-type']:
                    if request.GET.get('xhr2') == "true":
                        response["Access-Control-Allow-Origin"] =  "*";
                        response['Content-Type'] = requestInfo['content-type'];
                        response.write(result.read)
                    else:
                        response['Content-Type'] = "application/javascript";
                        if "text/html" in requestInfo['content-type'] or "application/xhtml" in requestInfo['content-type']:
                            htmlContent = result.read();
                            try:
                                response.write(request.GET.get('callback')+"("+json.dumps(htmlContent)+")"); 
                            except:
                                #this certainly isn't the best solution, but works for most common cases
                                response.write(request.GET.get('callback')+"("+json.dumps(unicode(htmlContent,"ISO-8859-1"))+")"); 
                        else:
                            response.write(request.GET.get('callback')+"("+json.dumps("data:" + requestInfo['content-type'] + ";base64," + base64.b64encode( result.read()) )+")");                   
                else:
                    response['Content-Type'] = "application/javascript";
                    response.write(request.GET.get('callback')+"("+json.dumps("error:Invalid mime:" + requestInfo['content-type']) +")" );
            else:
                response['Content-Type'] = "application/javascript";
                response.write(request.GET.get('callback')+"("+json.dumps( "error:Invalid protocol:" + urlInfo.scheme )+")" );

        except urllib2.URLError, e:
            response['Content-Type'] = "application/javascript";
            response.write(request.GET.get('callback')+"("+json.dumps( "error:Application error" ) +")" );

    return response
