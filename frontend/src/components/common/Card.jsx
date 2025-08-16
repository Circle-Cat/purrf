import "@/components/common/Card.css";

/**
 * Card Component
 *
 * A simple UI card that displays a title and a value.
 *
 * @component
 *
 * @param {Object} props
 * @param {string} props.title - The title text displayed at the top of the card.
 * @param {string|number} props.value - The value displayed below the title.
 *
 * @example
 * <Card title="Total Users" value={1024} />
 */

const Card = ({ title, value }) => {
  return (
    <div className="card" data-testid="card">
      <div className="card-title">{title}</div>
      <div className="card-value">{value}</div>
    </div>
  );
};

export default Card;
