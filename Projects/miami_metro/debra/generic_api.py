class ApiError(Exception):
    pass


class ApiContactingError(ApiError):
    pass

class Api404Error(ApiError):
    pass


class Resource(object):

    def __init__(self, api, value):
        self._api = api
        self._value = self._clean_value(value)

    @property
    def value(self):
        return self._value

    def _clean_value(self, value):
        return value

    def _call(self, endpoint, response, **params):
        return self._api._call(self.value, endpoint, response, **params)
        

class ResourceApi(object):
    ''' ResourceApi manages api calls to any Web API that receives particular
        main parameter (e.g. url, site etc)
    '''
    source_name = 'API'
    resource_class = Resource

    def __init__(self):
        self.__resources = {}

    def __getitem__(self, key):
        if key not in self.__resources:
            self.__resources[key] = self.resource_class(self, key)
        return self.__resources[key]

    def __setitem__(self, key, item):
        self.__resources[key] = item

    def _request(self, resource, endpoint, resp, **params):
        raise NotImplemented
        
    def _call(self, resource, endpoint, resp, **params):
        response = self._request(resource, endpoint, resp, **params)

        if response.status_code == 200:
            return resp(response.json())
        elif response.status_code == 404:
            return resp()
            # raise Api404Error()
        else:
            raise ApiContactingError(
                'there was an error contacting {}. status code:  {}'.format(
                    self.source_name, str(response.status_code)),
                response.status_code
            )