from pywebio import output

output.put_table([
    [output.span('Name',row=2), output.span('Address', col=2)],
    ['City', 'Country'],
    ['Wang', 'Beijing', 'China'],
    ['Liu', 'New York', 'America'],
])