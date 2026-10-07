#version 450

#pragma name StreamSharePane
#pragma format R8G8B8A8_UNORM
#pragma parameter LocalWidth "Local pane width" 0.5 0.01 1.0 0.01
#pragma parameter LocalHeight "Local pane height" 1.0 0.01 1.0 0.01

layout(set = 0, binding = 0, std140) uniform UBO {
    mat4 MVP;
    vec4 SourceSize;
    vec4 OutputSize;
    float LocalWidth;
    float LocalHeight;
};

#pragma stage vertex
layout(location = 0) in vec4 Position;
layout(location = 1) in vec2 TexCoord;
layout(location = 0) out vec2 vTexCoord;
void main() {
    gl_Position = MVP * Position;
    vTexCoord = TexCoord;
}

#pragma stage fragment
layout(location = 0) in vec2 vTexCoord;
layout(location = 0) out vec4 FragColor;
layout(binding = 1) uniform sampler2D Source;
void main() {
    if (vTexCoord.x >= LocalWidth || vTexCoord.y >= LocalHeight) {
        FragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }
    vec2 uv = vTexCoord / vec2(LocalWidth, LocalHeight);
    float sourceAspect = SourceSize.x / SourceSize.y;
    float paneAspect = (LocalWidth * OutputSize.x) / (LocalHeight * OutputSize.y);
    if (sourceAspect > paneAspect) {
        float height = paneAspect / sourceAspect;
        uv.y = (uv.y - (1.0 - height) * 0.5) / height;
    } else {
        float width = sourceAspect / paneAspect;
        uv.x = (uv.x - (1.0 - width) * 0.5) / width;
    }
    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
        FragColor = vec4(0.0, 0.0, 0.0, 1.0);
    } else {
        FragColor = vec4(texture(Source, uv).rgb, 1.0);
    }
}
