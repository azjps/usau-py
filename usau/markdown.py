"""
Utility functions for formatting pandas dataframes as markdown.

See http://stackoverflow.com/questions/13394140/generate-markdown-tables

Generates tables for Doxygen flavored Markdown.  See the Doxygen
documentation for details:
  http://www.stack.nl/~dimitri/doxygen/manual/markdown.html#md_tables.
"""

import pandas as pd

# Translation dictionaries for table alignment
left_rule = {'<': ':', '^': ':', '>': '-'}
right_rule = {'<': '-', '^': ':', '>': ':'}


def evaluate_field(record, field_spec, float_format=None):
    """Evaluate a field of a record using the type of the field_spec as a guide.

    float_format: lambda which returns a formatted string for a float
    """
    if type(field_spec) is int:
        value = record[field_spec]
        if isinstance(value, float):
            float_format = float_format or pd.get_option(
                'display.float_format')
            if float_format is not None:
                return float_format(value)
        return str(value)
    elif type(field_spec) is str:
        return str(getattr(record, field_spec))
    else:
        return str(field_spec(record))


def to_markdown(records, fields, headings, alignment=None, float_format=None):
    """Generate a Doxygen-flavor Markdown table from records.

    records: Iterable.  Rows will be generated from this.
    fields: List of fields for each row.  Each entry may be an integer,
        string or a function.  If the entry is an integer, it is assumed to be
        an index of each record.  If the entry is a string, it is assumed to be
        a field of each record.  If the entry is a function, it is called with
        the record and its return value is taken as the value of the field.
    headings (iterable[str]): List of column headings.
    alignment: List of pairs alignment characters.  The first of the pair
        specifies the alignment of the header, (Doxygen won't respect this, but
        it might look good, the second specifies the alignment of the cells in
        the column.

        Possible alignment characters are:
            '<' = Left align (default for cells)
            '>' = Right align
            '^' = Center (default for column headings)

    Returns:
        str: markdown table
    """

    num_columns = len(fields)
    assert len(headings) == num_columns

    # Compute the table cell data
    columns = [[] for i in range(num_columns)]
    for record in records:
        for i, field in enumerate(fields):
            columns[i].append(evaluate_field(
                record, field, float_format=float_format))

    # Fill out any missing alignment characters.
    extended_align = alignment if alignment != None else []
    if len(extended_align) > num_columns:
        extended_align = extended_align[0:num_columns]
    elif len(extended_align) < num_columns:
        extended_align += [('^', '<')
                           for i in range(num_columns - len(extended_align))]

    heading_align, cell_align = [x for x in zip(*extended_align)]

    field_widths = [len(max(column, key=len)) if len(column) > 0 else 0
                    for column in columns]
    heading_widths = [max(len(head), 2) for head in headings]
    column_widths = [max(x) for x in zip(field_widths, heading_widths)]

    _ = ' | '.join(['{:' + a + str(w) + '}'
                    for a, w in zip(heading_align, column_widths)])
    heading_template = '| ' + _ + ' |'
    _ = ' | '.join(['{:' + a + str(w) + '}'
                    for a, w in zip(cell_align, column_widths)])
    row_template = '| ' + _ + ' |'

    _ = ' | '.join([left_rule[a] + '-' * (w - 2) + right_rule[a]
                    for a, w in zip(cell_align, column_widths)])
    ruling = '| ' + _ + ' |'

    ret = u""
    ret += (heading_template.format(*headings).rstrip() + '\n')
    ret += (ruling.rstrip() + '\n')
    for row in zip(*columns):
        ret += (row_template.format(*row).rstrip() + '\n')
    return ret


def pandas_to_markdown(frame, alignment=None):
    """Convert a pandas dataframe to markdown"""
    return to_markdown(frame.values, list(range(len(frame.columns))), frame.columns,
                       alignment=alignment)


def display(frame, use_markdown=True):
    """Display as a HTML table in jupyter or as a markdown-formatted text table"""
    if use_markdown:
        print(pandas_to_markdown(frame))
    else:
        import IPython.display
        IPython.display.display(frame)
