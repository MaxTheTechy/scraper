import styles from './ImagePreview.module.css'

interface ImagePreviewProps {
  imagePath: string | null
  imageUrl: string | null
  title: string
}

// image_path is the local on-disk path under /data/images/ (e.g.
// "/data/images/abc123.jpg"); Nginx aliases /images/ -> /data/images/
// (spec Section 9), so the src we need is /images/<basename>. image_url is
// the *original remote* source URL and is not directly servable/reliable,
// so it's only used as a fallback link, never as an <img> src.
function toLocalImageSrc(imagePath: string | null): string | null {
  if (!imagePath) return null
  const basename = imagePath.split('/').pop()
  return basename ? `/images/${basename}` : null
}

export function ImagePreview({ imagePath, imageUrl, title }: ImagePreviewProps) {
  const src = toLocalImageSrc(imagePath)

  return (
    <div className={styles.wrapper}>
      {src ? (
        <img className={styles.image} src={src} alt={title} loading="lazy" />
      ) : (
        <div className={styles.placeholder}>No image</div>
      )}
      {imageUrl && (
        <a className={styles.sourceLink} href={imageUrl} target="_blank" rel="noreferrer">
          Original image source
        </a>
      )}
    </div>
  )
}
