import functions_framework

@functions_framework.http
def parse_xml(request):
    data = xmltodict.parse(request.data)
    print("data:")
    print(data)
    return "Hello World!"



