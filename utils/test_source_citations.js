const assert = require('node:assert');
const { transformSourceCitations } = require('../frontend/transforms');

// file:// prefix → link with /dufs/ href, display filename
{
    const input = 'See [Source: file:///documents/reports/Q1.pdf] for details';
    const result = transformSourceCitations(input);
    assert(result.includes('href="/dufs/reports/Q1.pdf"'), 'should rewrite to /dufs/ href');
    assert(result.includes('[Source: Q1.pdf]'), 'should display filename');
    assert(result.includes('class="source-citation"'), 'should have citation class');
    assert(result.includes('target="_blank"'), 'should open in new tab');
}

// bare /documents/ path (no file:// prefix)
{
    const input = 'Read [Source: /documents/handbook/governance.md] now';
    const result = transformSourceCitations(input);
    assert(result.includes('href="/dufs/handbook/governance.md"'), 'should rewrite bare path to /dufs/');
    assert(result.includes('[Source: governance.md]'), 'should display filename');
}

// no citations → unchanged
{
    const input = 'No citations here, just plain text.';
    const result = transformSourceCitations(input);
    assert.strictEqual(result, input, 'text without citations should be unchanged');
}

// multiple citations in one string
{
    const input = '[Source: /documents/a.txt] and [Source: file:///documents/b.pdf]';
    const result = transformSourceCitations(input);
    assert(result.includes('href="/dufs/a.txt"'), 'first citation should be transformed');
    assert(result.includes('href="/dufs/b.pdf"'), 'second citation should be transformed');
}

// encoded characters decoded in display name
{
    const input = '[Source: /documents/my%20report%20(final).pdf]';
    const result = transformSourceCitations(input);
    assert(result.includes('[Source: my report (final).pdf]'), 'should decode %20 in display name');
}

// non-/documents/ path → left as plain text
{
    const input = '[Source: /other/path/file.txt]';
    const result = transformSourceCitations(input);
    assert.strictEqual(result, input, 'non-/documents/ path should be unchanged');
}

// HTML in filename is escaped (XSS prevention)
{
    const input = '[Source: /documents/<script>alert(1)<\/script>.pdf]';
    const result = transformSourceCitations(input);
    assert(!result.includes('<script>'), 'should escape < in filename');
    assert(result.includes('&lt;script&gt;'), 'should HTML-encode < and > in display name');
}

// double-quote in path is escaped in title attribute
{
    const input = '[Source: /documents/say"hello".pdf]';
    const result = transformSourceCitations(input);
    assert(result.includes('title="/documents/say&quot;hello&quot;.pdf"'), 'should escape " in title attribute');
}

console.log('All tests passed.');
