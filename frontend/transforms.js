function transformSourceCitations(html) {
    return html.replace(
        /\[Source:\s*((?:file:\/\/)?\/documents\/[^\]]+?)\s*\]/g,
        function(match, rawPath) {
            let filePath = rawPath.replace(/^file:\/\//, '');
            let dufsUrl = filePath.replace(/^\/documents\//, '/dufs/');
            let fileName = decodeURIComponent(filePath.split('/').pop());
            // Fix 1: escape HTML special chars in fileName before inserting into link text
            fileName = fileName.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            // Fix 2: escape HTML special chars in filePath before inserting into title attribute
            let safeTitle = filePath.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
            return '<a class="source-citation" href="' + encodeURI(dufsUrl) + '" target="_blank" title="' + safeTitle + '">[Source: ' + fileName + ']</a>';
        }
    );
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { transformSourceCitations };
}
