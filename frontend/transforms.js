function transformSourceCitations(html) {
    return html.replace(
        /\[Source:\s*((?:file:\/\/)?\/documents\/[^\]]+?)\s*\]/g,
        function(match, rawPath) {
            let filePath = rawPath.replace(/^file:\/\//, '');
            let dufsUrl = filePath.replace(/^\/documents\//, '/dufs/');
            let fileName = decodeURIComponent(filePath.split('/').pop());
            return '<a class="source-citation" href="' + encodeURI(dufsUrl) + '" target="_blank" title="' + filePath + '">[Source: ' + fileName + ']</a>';
        }
    );
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { transformSourceCitations };
}
